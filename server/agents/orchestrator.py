"""The Orchestrator: an ADK LlmAgent with the read-only ward tools attached
directly, and output_schema enforcing the narrative+claims answer format.

MVP simplification (see docs/DECISIONS.md): CLAUDE.md describes a separate
Geospatial Analyst sub-agent that the Orchestrator delegates to. This
version gives the Orchestrator the tools directly instead. ADK's real
multi-agent delegation (sub_agents + transfer_to_agent) is a second layer
of moving parts on top of getting tool-calling + structured output + the
verifier working end-to-end; splitting it out is a follow-on now that the
base path is proven, not a permanent design choice.
"""

import functools
import os

from google.adk.agents.llm_agent import Agent

from server.agents.schemas import Answer
from server.optimizer.plan import run_plan
from server.store import ToolResultStore
from server.tools import interventions as interventions_tools
from server.tools import wards as wards_tools

MODEL_ID = os.environ.get("MODEL_ID", "gemini-2.5-flash")

INSTRUCTION = """You help city planners understand heat risk across Bengaluru's 369 wards.

city_id is always 'bengaluru'. The current year is 2025 unless the question
asks otherwise; the baseline year for change-over-time questions is 2016.

Use the tools to gather every fact and number you need. Never state a
number, ward name, or ranking that did not come from a tool result -- you
have no other source of truth about the data.

Your final answer must follow the required output format exactly: every
single number or ward name in the narrative is written as a placeholder
token, never directly as text, with a matching entry in the claims list
that cites the exact tool_result_id and data path it came from. See the
output schema field descriptions for the exact token shape and examples.

find_ward returns only names and keys. To state any metric for a ward,
first call the tool that returns it (for example get_ward_metrics with the
ward_key from find_ward). Only cite a tool_result_id that a tool call in
this conversation actually returned.
"""


def _bind_tools(store: ToolResultStore):
    def get_ward_metrics(city_id: str, ward_key: str, year: int) -> dict:
        """Get every metric (surface temperature, NDVI, built-up fraction,
        population, composite risk, rank, change since baseline) for one
        specific ward in one year."""
        return wards_tools.get_ward_metrics(store, city_id, ward_key, year)

    def find_ward(city_id: str, name_query: str) -> dict:
        """Find candidate wards by a name the user typed, which may be
        misspelled or in Kannada. Returns ranked candidates -- never assume
        the first one is correct if the question depends on getting the
        right ward; check the ward_name in the result against what the user
        asked for."""
        return wards_tools.find_ward(store, city_id, name_query)

    def rank_wards(city_id: str, metric: str, n: int, year: int, corporation: str = "", order: str = "desc") -> dict:
        """Rank wards by a metric and return the top n. metric must be one
        of: lst_mean_c, lst_max_c, ndvi_mean, built_frac, valid_pixel_frac,
        composite_risk, delta_lst_c, population. order is 'desc' (highest
        first) or 'asc' (lowest first). Set corporation to filter to one
        corporation (Central, East, North, South, West), or leave it empty
        for citywide."""
        return wards_tools.rank_wards(store, city_id, metric, n, year, corporation or None, order)

    def compare_years(city_id: str, ward_keys: list[str], metric: str, year_a: int, year_b: int) -> dict:
        """Compare a metric for specific wards between two years. metric
        must be one of: lst_mean_c, lst_max_c, ndvi_mean, built_frac,
        valid_pixel_frac, composite_risk, delta_lst_c."""
        return wards_tools.compare_years(store, city_id, ward_keys, metric, year_a, year_b)

    def corporation_summary(city_id: str, corporation: str, year: int) -> dict:
        """Get averaged metrics and total population for one corporation
        (Central, East, North, South, West) in one year."""
        return wards_tools.corporation_summary(store, city_id, corporation, year)

    def nearby_facilities(city_id: str, ward_key: str, type: str = "") -> dict:
        """Count and list hospitals and schools in one ward. Set type to
        'hospital' or 'school' to filter, or leave it empty for both."""
        return wards_tools.nearby_facilities(store, city_id, ward_key, type or None)

    def live_regionstats(ward_key: str, layer: str, year: int) -> dict:
        """Recompute one ward's statistic live from the satellite raster,
        instead of the precomputed table -- use this only when the user
        specifically asks for a live or freshly-recomputed figure. layer
        must be one of: lst, ndvi, built. year must be 2016 or 2025."""
        return wards_tools.live_regionstats(store, ward_key, layer, year)

    def recommend_interventions(city_id: str, ward_key: str, year: int = 2025) -> dict:
        """Recommend applicable heat-reducing interventions for one ward
        (tree canopy, lake/wetland buffer restoration, pocket parks, cool
        roofs, permeable paving), each with an assumed cost and, where the
        cooling model supports it, a modeled surface-temperature effect
        range citing a real published source. Some interventions have no
        quantified cooling effect (cool roofs, permeable paving) -- say so
        plainly rather than implying a number that doesn't exist."""
        return interventions_tools.recommend_interventions(store, city_id, ward_key, year)

    def intervention_catalog(city_id: str) -> dict:
        """List every intervention in the city's catalog (tree canopy, lake
        and wetland buffers, pocket parks, cool roofs, permeable paving) with
        its unit, assumed cost per unit in INR and citations. Use this for
        questions about costs or units that are not about one ward."""
        return interventions_tools.intervention_catalog(store, city_id)

    def plan_budget(city_id: str, budget_inr: float, corporation: str = "") -> dict:
        """Plan how to spend a cooling budget in rupees across wards, for the
        whole city or one corporation (Central, East, North, South, West).
        Returns the optimized allocation, the naive "fund the hottest wards
        first" allocation, a comparison of modeled person-°C and people
        covered for both, and the assumptions. All costs are assumed costs
        and all cooling is a modeled association -- say so."""
        return run_plan(store, city_id, corporation or None, budget_inr)

    def timed(fn):
        # functools.wraps keeps the signature and docstring ADK reads to
        # build each tool's schema.
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            store.mark_start()
            return fn(*args, **kwargs)
        return wrapper

    return [timed(f) for f in (
        get_ward_metrics, find_ward, rank_wards, compare_years,
        corporation_summary, nearby_facilities, live_regionstats,
        recommend_interventions, intervention_catalog, plan_budget,
    )]


def build_orchestrator(store: ToolResultStore) -> Agent:
    return Agent(
        model=MODEL_ID,
        name="orchestrator",
        description="Answers planning questions about Bengaluru's ward-level heat risk using verified data tools.",
        instruction=INSTRUCTION,
        tools=_bind_tools(store),
        output_schema=Answer,
    )
