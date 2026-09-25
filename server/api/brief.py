from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from google.cloud import bigquery

from server.store import ToolResultStore
from server.tools.bq import DATASET, PROJECT, run_query
from server.tools.interventions import recommend_interventions
from server.tools.wards import BASELINE_YEAR, compare_to_city_median, compare_years, get_ward_metrics, nearby_facilities

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
    "sources": "ಮೂಲಗಳು",
    "generated": "ರಚಿಸಲಾದ ದಿನಾಂಕ",
}
_LABELS_EN = {
    "ward_brief": "Ward brief",
    "corporation": "Corporation",
    "key_figures": "Key figures",
    "recommended_actions": "Recommended actions",
    "assumptions": "Assumptions",
    "limitations": "Limitations",
    "sources": "Sources",
    "generated": "Generated",
}

_LIMITATIONS = [
    "Land surface temperature is not air temperature.",
    "Each year is one pre-monsoon (March to May) composite, so a change between two years can reflect that season's weather, not only a long-term trend.",
    "Population figures are 2011 Census counts apportioned to the 2025 ward boundaries, not a fresh count.",
    "Effect ranges are modeled associations from a model with a held-out R² of about 0.26, not guaranteed outcomes.",
    "Costs marked as assumptions are placeholder estimates until sourced from a vendor or BBMP quote.",
]


def _guidance_documents(city_id: str) -> list[dict]:
    sql = f"SELECT doc_id, title, publisher, url, doc_date FROM `{PROJECT}.{DATASET}.guidance_documents` WHERE city_id = @city_id"
    return run_query(sql, [bigquery.ScalarQueryParameter("city_id", "STRING", city_id)])


@router.get("/brief/{ward_key}")
def ward_brief(ward_key: str, lang: str = Query("en", pattern="^(en|kn)$"), year: int = 2025, city_id: str = "bengaluru"):
    store = ToolResultStore()
    ward_result = get_ward_metrics(store, city_id, ward_key, year)
    if ward_result["data"] is None:
        raise HTTPException(status_code=404, detail=f"No ward '{ward_key}' for {city_id}/{year}")

    baseline_result = get_ward_metrics(store, city_id, ward_key, BASELINE_YEAR)
    median_result = compare_to_city_median(store, city_id, ward_key, year)
    interventions_result = recommend_interventions(store, city_id, ward_key, year)
    facilities_result = nearby_facilities(store, city_id, ward_key)
    green_change = compare_years(store, city_id, [ward_key], "ndvi_mean", BASELINE_YEAR, year)
    built_change = compare_years(store, city_id, [ward_key], "built_frac", BASELINE_YEAR, year)

    return {
        "labels": _LABELS_KN if lang == "kn" else _LABELS_EN,
        "lang": lang,
        "unverified_translation": lang == "kn",
        "year": year,
        "baseline_year": BASELINE_YEAR,
        "season": "Pre-monsoon (March to May)",
        "ward": ward_result["data"],
        "baseline": baseline_result["data"],
        "city_median": median_result["data"],
        "recommended_actions": interventions_result["data"]["recommendations"] if interventions_result["data"] else [],
        "facilities": facilities_result["data"],
        "changes": {
            "ndvi_mean": green_change["data"][0] if green_change["data"] else None,
            "built_frac": built_change["data"][0] if built_change["data"] else None,
        },
        "guidance_documents": _guidance_documents(city_id),
        "limitations": _LIMITATIONS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_result_ids": {
            "ward": ward_result["tool_result_id"],
            "baseline": baseline_result["tool_result_id"],
            "city_median": median_result["tool_result_id"],
            "interventions": interventions_result["tool_result_id"],
            "facilities": facilities_result["tool_result_id"],
            "green_change": green_change["tool_result_id"],
            "built_change": built_change["tool_result_id"],
        },
        "sources": store.sources(),
    }
