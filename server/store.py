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


class ToolResultStore:
    def __init__(self):
        self._results: dict[str, dict] = {}

    def record(self, tool_name: str, params: dict, data) -> dict:
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
