from fastapi import APIRouter, HTTPException
from google.cloud import bigquery
from pydantic import BaseModel, Field

from server.optimizer.allocator import DEFAULT_PER_WARD_CAP_FRACTION, MAX_UNITS_PER_PAIR, naive_allocate, optimize
from server.store import ToolResultStore
from server.tools.bq import DATASET, PROJECT, run_query
from server.tools.interventions import bulk_recommend_interventions

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
    options = bulk_recommend_interventions(store, request.city_id, request.corporation, request.year)
    wards = options["data"]["wards"]
    if not wards:
        raise HTTPException(status_code=404, detail=f"No wards found for corporation {request.corporation!r}.")

    for ward in wards:
        for iv in ward["interventions"]:
            if iv["intervention_id"] in request.cost_overrides:
                iv["cost_inr_per_unit"] = request.cost_overrides[iv["intervention_id"]]
                iv["cost_is_assumption"] = True

    optimized = optimize(wards, request.budget_inr)
    naive = naive_allocate(wards, request.budget_inr)

    assumptions = [
        "Only tree canopy, lake and wetland buffer restoration, and pocket parks have a modeled cooling effect, through the NDVI term of the cooling model. Cool roofs and permeable paving have no modeled ward-level effect, so the plan cannot count cooling for them.",
        "Every unit cost is an assumed cost, not a sourced quote."
        + (f" You changed: {', '.join(sorted(request.cost_overrides))}." if request.cost_overrides else ""),
        f"Each ward and intervention pair can be funded up to {MAX_UNITS_PER_PAIR} units, and no ward can take more than {int(DEFAULT_PER_WARD_CAP_FRACTION * 100)}% of the budget. No diminishing returns are modeled below those caps.",
        "Cooling figures are modeled associations with surface temperature (held-out R² about 0.26), not guaranteed outcomes.",
        "Person-°C is modeled ward cooling multiplied by the ward's 2011 Census population apportioned to 2025 boundaries.",
    ]

    result = {
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
        {"city_id": request.city_id, "corporation": request.corporation, "budget_inr": request.budget_inr,
         "cost_overrides": request.cost_overrides, "year": request.year},
        result,
    )
    return {**result, "tool_result_id": recorded["tool_result_id"], "options_tool_result_id": options["tool_result_id"]}
