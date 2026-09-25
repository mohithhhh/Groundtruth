import os

from google.cloud import bigquery

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "penumbra-509416")
DATASET = os.environ.get("BQ_DATASET", "penumbra")

_client = bigquery.Client(project=PROJECT)

# Running total across the process, read by eval/run_eval.py for cost.
stats = {"bytes_billed": 0}


def run_query(sql: str, params: list[bigquery.ScalarQueryParameter] | None = None) -> list[dict]:
    """Every tool call goes through here: parameterized SQL only, with a
    billing cap, per CLAUDE.md's read-only-at-request-time rule."""
    job_config = bigquery.QueryJobConfig(
        query_parameters=params or [],
        maximum_bytes_billed=200_000_000,
    )
    job = _client.query(sql, job_config=job_config)
    rows = [dict(row) for row in job.result()]
    stats["bytes_billed"] += job.total_bytes_billed or 0
    return rows
