"""Every tool call gets a tool_result_id. The in-memory map serves the
current request (assembling claims/trace); the BigQuery table is the
durable audit trail behind GET /api/sources/{tool_result_id} -- it must
work even if a later request lands on a different Cloud Run instance.
"""

import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from google.cloud import bigquery

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "penumbra-509416")
DATASET = os.environ.get("BQ_DATASET", "penumbra")
TABLE = f"{PROJECT}.{DATASET}.tool_results"

_client = bigquery.Client(project=PROJECT)
_executor = ThreadPoolExecutor(max_workers=2)


class ToolCallLimitExceeded(Exception):
    pass


class ToolResultStore:
    """max_calls guards a single /api/ask request against runaway tool use
    (CLAUDE.md: "at most 8 tool calls per question")."""

    def __init__(self, max_calls: int = 8):
        self._results: dict[str, dict] = {}
        self._max_calls = max_calls
        self._pending_start: float | None = None

    def mark_start(self) -> None:
        """Called just before a tool runs, so the trace can separate the
        tool's own run time from the model's thinking time before it."""
        self._pending_start = time.time()

    def record(self, tool_name: str, params: dict, data) -> dict:
        if len(self._results) >= self._max_calls:
            raise ToolCallLimitExceeded(f"exceeded {self._max_calls} tool calls for this question")
        tool_result_id = str(uuid.uuid4())
        now = time.time()
        entry = {
            "tool_result_id": tool_result_id,
            "tool_name": tool_name,
            "params": params,
            "data": data,
            "started_at": self._pending_start or now,
            "created_at": now,
        }
        self._pending_start = None
        self._results[tool_result_id] = entry
        _executor.submit(_write_to_bigquery, entry)
        return {"tool_result_id": tool_result_id, "data": data}

    def get(self, tool_result_id: str) -> dict | None:
        """In-process lookup only -- valid for the lifetime of this request/
        session. Use fetch_from_bigquery for a cross-instance-safe lookup."""
        return self._results.get(tool_result_id)

    def sources(self) -> list[dict]:
        """Plain-language description of every tool call made so far, for
        responses that list their sources inline (e.g. the printed brief)."""
        return [
            {
                "tool_result_id": e["tool_result_id"],
                "tool_name": e["tool_name"],
                "description": _describe_tool_call(e["tool_name"], e["params"]),
                "created_at": datetime.fromtimestamp(e["created_at"], tz=timezone.utc).isoformat(),
            }
            for e in self._results.values()
        ]

    def trace(self, start_time: float, answered_at: float) -> list[dict]:
        """A real sequence of steps with durations, built from actual tool
        calls in the order they happened (Python dicts preserve insertion
        order) -- for the Ask page's "how this answer was made" panel.
        Model time before the first tool is "Planned the steps"; each tool
        step is that tool's own run time; model time after the last tool is
        "Wrote the answer"."""
        entries = list(self._results.values())
        first_start = entries[0]["started_at"] if entries else answered_at
        steps = [{"step": 1, "description": "Planned the steps", "duration_s": round(first_start - start_time, 3)}]
        for entry in entries:
            steps.append({
                "step": len(steps) + 1,
                "description": _describe_tool_call(entry["tool_name"], entry["params"]),
                "duration_s": round(entry["created_at"] - entry["started_at"], 3),
            })
        if entries:
            steps.append({"step": len(steps) + 1, "description": "Wrote the answer", "duration_s": round(answered_at - entries[-1]["created_at"], 3)})
        return steps

_METRIC_LABELS = {
    "lst_mean_c": "surface temperature",
    "lst_max_c": "peak surface temperature",
    "ndvi_mean": "green cover",
    "built_frac": "built-up share",
    "valid_pixel_frac": "cloud-free coverage",
    "composite_risk": "heat risk score",
    "delta_lst_c": "change in surface temperature",
    "population": "population",
}
_BASELINE_YEAR = 2016


def _metric(name: str) -> str:
    return _METRIC_LABELS.get(name, name)


def _describe_tool_call(tool_name: str, params: dict) -> str:
    if tool_name == "rank_wards":
        scope = f"{params['corporation']} corporation" if params.get("corporation") else "whole city"
        years = f"{_BASELINE_YEAR} to {params['year']}" if params["metric"] == "delta_lst_c" else str(params["year"])
        return f"Ranked wards by {_metric(params['metric'])}, {scope}, {years}"
    if tool_name == "get_ward_metrics":
        return f"Looked up {params['year']} figures for ward {params['ward_key']}"
    if tool_name == "find_ward":
        return f"Searched for a ward matching '{params['name_query']}'"
    if tool_name == "compare_years":
        return f"Compared {_metric(params['metric'])} between {params['year_a']} and {params['year_b']}"
    if tool_name == "corporation_summary":
        return f"Summarized {params['corporation']} corporation, {params['year']}"
    if tool_name == "nearby_facilities":
        return f"Looked up facilities near {params['ward_key']}"
    if tool_name == "live_regionstats":
        layer = {"lst": "surface temperature", "ndvi": "green cover", "built": "built-up share"}.get(params["layer"], params["layer"])
        return f"Recomputed {layer} for {params['year']} live from the satellite image, ward {params['ward_key']}"
    if tool_name == "recommend_interventions":
        return f"Matched cooling interventions to {params['ward_key']}"
    if tool_name == "bulk_recommend_interventions":
        scope = f"{params['corporation']} corporation" if params.get("corporation") else "the whole city"
        return f"Matched cooling interventions to every ward in {scope}"
    if tool_name == "budget_plan":
        scope = f"{params['corporation']} corporation" if params.get("corporation") else "the whole city"
        return f"Allocated a Rs {params['budget_inr']:,.0f} budget across {scope}, and the hottest-first comparison"
    if tool_name == "compare_to_city_median":
        return f"Compared {params['ward_key']} with the city median surface temperature, {params['year']}"
    return f"Called {tool_name}"


def _write_to_bigquery(entry: dict) -> None:
    row = {
        "tool_result_id": entry["tool_result_id"],
        "tool_name": entry["tool_name"],
        "params_json": json.dumps(entry["params"], default=str),
        "result_json": json.dumps(entry["data"], default=str),
        "created_at": datetime.fromtimestamp(entry["created_at"], tz=timezone.utc).isoformat(),
    }
    errors = _client.insert_rows_json(TABLE, [row])
    if errors:
        print(f"tool_results insert failed: {errors}")


def fetch_from_bigquery(tool_result_id: str) -> dict | None:
    query = f"""
    SELECT tool_name, params_json, result_json, created_at
    FROM `{TABLE}`
    WHERE tool_result_id = @tool_result_id
    ORDER BY created_at DESC
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("tool_result_id", "STRING", tool_result_id)],
        maximum_bytes_billed=100_000_000,
    )
    rows = list(_client.query(query, job_config=job_config).result())
    if not rows:
        return None
    row = rows[0]
    params = json.loads(row.params_json)
    return {
        "tool_name": row.tool_name,
        "description": _describe_tool_call(row.tool_name, params),
        "params": params,
        "data": json.loads(row.result_json),
        "created_at": row.created_at.isoformat(),
    }
