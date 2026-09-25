"""One budget plan: every ward's options, the optimized allocation and the
naive hottest-first allocation, recorded as a single budget_plan tool
result. Shared by POST /api/plan and the Ask agent's plan_budget tool."""

from server.optimizer.allocator import DEFAULT_PER_WARD_CAP_FRACTION, MAX_UNITS_PER_PAIR, naive_allocate, optimize
from server.store import ToolResultStore
from server.tools.interventions import bulk_recommend_interventions


class EmptyScope(ValueError):
    pass


def run_plan(
    store: ToolResultStore, city_id: str, corporation: str | None, budget_inr: float,
    year: int = 2025, cost_overrides: dict[str, float] | None = None,
) -> dict:
    cost_overrides = cost_overrides or {}
    options = bulk_recommend_interventions(store, city_id, corporation, year)
    wards = options["data"]["wards"]
    if not wards:
        raise EmptyScope(f"No wards found for corporation {corporation!r}.")

    for ward in wards:
        for iv in ward["interventions"]:
            if iv["intervention_id"] in cost_overrides:
                iv["cost_inr_per_unit"] = cost_overrides[iv["intervention_id"]]
                iv["cost_is_assumption"] = True

    optimized = optimize(wards, budget_inr)
    naive = naive_allocate(wards, budget_inr)

    assumptions = [
        "Only tree canopy, lake and wetland buffer restoration, and pocket parks have a modeled cooling effect, through the NDVI term of the cooling model. Cool roofs and permeable paving have no modeled ward-level effect, so the plan cannot count cooling for them.",
        "Every unit cost is an assumed cost, not a sourced quote."
        + (f" You changed: {', '.join(sorted(cost_overrides))}." if cost_overrides else ""),
        f"Each ward and intervention pair can be funded up to {MAX_UNITS_PER_PAIR} units, and no ward can take more than {int(DEFAULT_PER_WARD_CAP_FRACTION * 100)}% of the budget. No diminishing returns are modeled below those caps.",
        "Cooling figures are modeled associations with surface temperature (held-out R² about 0.26), not guaranteed outcomes.",
        "Person-°C is modeled ward cooling multiplied by the ward's 2011 Census population apportioned to 2025 boundaries.",
    ]

    result = {
        "budget_inr": budget_inr,
        "allocation": optimized["allocation"],
        "naive": naive["allocation"],
        "comparison": {
            "optimized_total_person_c": optimized["total_person_c"],
            "naive_total_person_c": naive["total_person_c"],
            "optimized_people_covered": optimized["people_covered"],
            "naive_people_covered": naive["people_covered"],
            "optimized_wards_covered": optimized["wards_covered"],
            "naive_wards_covered": naive["wards_covered"],
            "optimized_cost_inr": optimized["total_cost_inr"],
            "naive_cost_inr": naive["total_cost_inr"],
        },
        "assumptions": assumptions,
    }
    recorded = store.record(
        "budget_plan",
        {"city_id": city_id, "corporation": corporation, "budget_inr": budget_inr,
         "cost_overrides": cost_overrides, "year": year},
        result,
    )
    return {**recorded, "options_tool_result_id": options["tool_result_id"]}
