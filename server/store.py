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

    def record(self, tool_name: str, params: dict, data) -> dict:
        if len(self._results) >= self._max_calls:
            raise ToolCallLimitExceeded(f"exceeded {self._max_calls} tool calls for this question")
        tool_result_id = str(uuid.uuid4())
        entry = {
            "tool_result_id": tool_result_id,
            "tool_name": tool_name,
            "params": params,
            "data": data,
            "created_at": time.time(),
        }
        self._results[tool_result_id] = entry
        _executor.submit(_write_to_bigquery, entry)
        return {"tool_result_id": tool_result_id, "data": data}

    def get(self, tool_result_id: str) -> dict | None:
        """In-process lookup only -- valid for the lifetime of this request/
        session. Use fetch_from_bigquery for a cross-instance-safe lookup."""
        return self._results.get(tool_result_id)

    def trace(self, start_time: float) -> list[dict]:
        """A real sequence of steps with durations, built from actual tool
        calls in the order they happened (Python dicts preserve insertion
        order) -- for the Ask page's "how this answer was made" panel."""
        steps = []
        previous_time = start_time
        first_call_time = next(iter(self._results.values()), {}).get("created_at", start_time)
        steps.append({"step": 1, "description": "Planned the steps", "duration_s": round(first_call_time - start_time, 3)})
        for i, entry in enumerate(self._results.values(), start=2):
            steps.append({
                "step": i,
                "description": _describe_tool_call(entry["tool_name"], entry["params"]),
                "duration_s": round(entry["created_at"] - previous_time, 3),
            })
            previous_time = entry["created_at"]
        return steps


def _describe_tool_call(tool_name: str, params: dict) -> str:
    if tool_name == "rank_wards":
        scope = f"in {params['corporation']} corporation" if params.get("corporation") else "citywide"
        return f"Ranked wards by {params['metric']} ({scope})"
    if tool_name == "get_ward_metrics":
        return f"Looked up metrics for {params['ward_key']}"
    if tool_name == "find_ward":
        return f"Searched for a ward matching '{params['name_query']}'"
    if tool_name == "compare_years":
        return f"Compared {params['metric']} between {params['year_a']} and {params['year_b']}"
    if tool_name == "corporation_summary":
        return f"Summarized {params['corporation']} corporation"
    if tool_name == "nearby_facilities":
        return f"Looked up facilities near {params['ward_key']}"
    if tool_name == "live_regionstats":
        return f"Recomputed {params['layer']} live for {params['ward_key']}"
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
    return {
        "tool_name": row.tool_name,
        "params": json.loads(row.params_json),
        "data": json.loads(row.result_json),
        "created_at": row.created_at.isoformat(),
    }
