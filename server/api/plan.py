from fastapi import APIRouter, HTTPException
from google.cloud import bigquery
from pydantic import BaseModel, Field

from server.optimizer.plan import EmptyScope, run_plan
from server.store import ToolResultStore
from server.tools.bq import DATASET, PROJECT, run_query

router = APIRouter()


class PlanRequest(BaseModel):
    budget_inr: float
    corporation: str | None = None  # None = whole city
    cost_overrides: dict[str, float] = Field(default_factory=dict)  # intervention_id -> INR per unit
    city_id: str = "bengaluru"
    year: int = 2025


@router.get("/interventions")
def list_interventions(city_id: str = "bengaluru"):
    """The catalog behind the Plan page's editable cost list."""
    sql = f"""
    SELECT intervention_id, name, unit, model_pathway_type, model_pathway_description,
      cost_amount_inr_per_unit, cost_is_assumption, cost_note, cited_fact_text, citations
    FROM `{PROJECT}.{DATASET}.intervention_catalog`
    WHERE city_id = @city_id
    ORDER BY model_pathway_type, intervention_id
    """
    return run_query(sql, [bigquery.ScalarQueryParameter("city_id", "STRING", city_id)])


@router.post("/plan")
def plan(request: PlanRequest):
    if request.budget_inr <= 0:
        raise HTTPException(status_code=400, detail="Enter a budget above zero.")
    bad = {k: v for k, v in request.cost_overrides.items() if v <= 0}
    if bad:
        raise HTTPException(status_code=400, detail=f"Costs must be above zero: {', '.join(bad)}")

    store = ToolResultStore(max_calls=4)
    try:
        recorded = run_plan(store, request.city_id, request.corporation, request.budget_inr, request.year, request.cost_overrides)
    except EmptyScope as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {**recorded["data"], "tool_result_id": recorded["tool_result_id"], "options_tool_result_id": recorded["options_tool_result_id"]}
