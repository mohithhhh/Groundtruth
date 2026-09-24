from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from server.store import ToolResultStore
from server.tools.interventions import recommend_interventions
from server.tools.wards import get_ward_metrics, nearby_facilities

router = APIRouter()

# Section labels only -- prose (ward names, figures, citation quotes) stays
# in English. Written from general Kannada knowledge, not run through a
# translation API or reviewed by a certified/native translator -- flagged
# as unverified in the response, per CLAUDE.md's "mark machine-translated
# prose as such."
_LABELS_KN = {
    "ward_brief": "ವಾರ್ಡ್ ಸಂಕ್ಷಿಪ್ತ ವರದಿ",
    "corporation": "ಪಾಲಿಕೆ",
    "key_figures": "ಪ್ರಮುಖ ಅಂಕಿಅಂಶಗಳು",
    "recommended_actions": "ಶಿಫಾರಸು ಮಾಡಿದ ಕ್ರಮಗಳು",
    "assumptions": "ಊಹೆಗಳು",
    "limitations": "ಮಿತಿಗಳು",
    "generated": "ರಚಿಸಲಾದ ದಿನಾಂಕ",
}
_LABELS_EN = {
    "ward_brief": "Ward brief",
    "corporation": "Corporation",
    "key_figures": "Key figures",
    "recommended_actions": "Recommended actions",
    "assumptions": "Assumptions",
    "limitations": "Limitations",
    "generated": "Generated",
}

_LIMITATIONS = [
    "Land surface temperature is not air temperature.",
    "Population figures are 2011 Census counts apportioned to the 2025 ward boundaries, not a fresh count.",
    "Effect ranges are modeled associations, not guaranteed outcomes -- see model/README.md.",
    "Costs marked as assumptions are placeholder estimates until sourced from a vendor or BBMP quote.",
]


@router.get("/brief/{ward_key}")
def ward_brief(ward_key: str, lang: str = Query("en", pattern="^(en|kn)$"), year: int = 2025, city_id: str = "bengaluru"):
    store = ToolResultStore()
    ward_result = get_ward_metrics(store, city_id, ward_key, year)
    if ward_result["data"] is None:
        raise HTTPException(status_code=404, detail=f"No ward '{ward_key}' for {city_id}/{year}")

    interventions_result = recommend_interventions(store, city_id, ward_key, year)
    facilities_result = nearby_facilities(store, city_id, ward_key)

    labels = _LABELS_KN if lang == "kn" else _LABELS_EN

    return {
        "labels": labels,
        "lang": lang,
        "unverified_translation": lang == "kn",
        "ward": ward_result["data"],
        "recommended_actions": interventions_result["data"]["recommendations"] if interventions_result["data"] else [],
        "facilities": facilities_result["data"],
        "limitations": _LIMITATIONS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_result_ids": {
            "ward": ward_result["tool_result_id"],
            "interventions": interventions_result["tool_result_id"],
            "facilities": facilities_result["tool_result_id"],
        },
    }
