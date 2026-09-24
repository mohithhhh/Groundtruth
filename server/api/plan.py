from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.optimizer.allocator import naive_allocate, optimize
from server.store import ToolResultStore
from server.tools.interventions import bulk_recommend_interventions

router = APIRouter()


class PlanRequest(BaseModel):
    budget_inr: float
    corporation: str | None = None  # None = whole city
    city_id: str = "bengaluru"
    year: int = 2025


@router.post("/plan")
def plan(request: PlanRequest):
    if request.budget_inr <= 0:
        raise HTTPException(status_code=400, detail="budget_inr must be positive")

    store = ToolResultStore(max_calls=100)  # a planning request legitimately touches every ward in scope
    result = bulk_recommend_interventions(store, request.city_id, request.corporation, request.year)
    wards = result["data"]["wards"]
    if not wards:
        raise HTTPException(status_code=404, detail=f"No wards found for corporation={request.corporation!r}")

    optimized = optimize(wards, request.budget_inr)
    naive = naive_allocate(wards, request.budget_inr)

    return {
        "allocation": optimized["allocation"],
        "naive": naive["allocation"],
        "comparison": {
            "optimized_total_person_c": optimized["total_person_c"],
            "naive_total_person_c": naive["total_person_c"],
            "optimized_people_covered": optimized["people_covered"],
            "naive_people_covered": naive["people_covered"],
            "optimized_wards_covered": optimized["wards_covered"],
            "naive_wards_covered": naive["wards_covered"],
        },
        "assumptions": [
            "Only tree canopy, lake/wetland buffer restoration, and pocket parks have a quantified cooling effect (via the NDVI pathway in the cooling model); cool roofs and permeable paving have no modeled ward-level cooling effect and are excluded from the person-C optimization even though their real (assumed) cost is in the catalog.",
            "Every intervention's unit cost is a placeholder assumption (cost_is_assumption: true in the catalog), not a sourced quote.",
            "Each ward/intervention pair may be funded up to 5 units; no diminishing returns are modeled beyond that cap and the per-ward spending cap (15% of budget by default).",
            "Effect ranges are modeled associations with surface temperature (LST), not guaranteed outcomes -- see model/README.md for the cooling model's held-out accuracy.",
        ],
        "tool_result_id": result["tool_result_id"],
    }
