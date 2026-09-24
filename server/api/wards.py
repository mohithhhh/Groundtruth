from fastapi import APIRouter, HTTPException
from google.cloud import bigquery

from server.store import ToolResultStore, fetch_from_bigquery
from server.tools.bq import PROJECT, DATASET, run_query
from server.tools.wards import get_ward_metrics

router = APIRouter()
_T = f"{PROJECT}.{DATASET}"


@router.get("/wards")
def list_wards(year: int = 2025, city_id: str = "bengaluru"):
    """Bulk listing for the map and ranked list -- not an agent tool call,
    so it queries directly rather than going through the tool store."""
    sql = f"""
    SELECT
      w.ward_key, w.ward_name, w.ward_name_kn, w.corporation,
      m.lst_mean_c, m.ndvi_mean, m.built_frac,
      r.composite_risk, r.rank, r.delta_lst_c
    FROM `{_T}.wards_clean` AS w
    JOIN `{_T}.ward_metrics` AS m ON m.ward_key = w.ward_key AND m.year = @year
    LEFT JOIN `{_T}.ward_risk` AS r ON r.ward_key = w.ward_key AND r.year = @year
    WHERE w.city_id = @city_id
    ORDER BY r.rank
    """
    params = [
        bigquery.ScalarQueryParameter("year", "INT64", year),
        bigquery.ScalarQueryParameter("city_id", "STRING", city_id),
    ]
    return run_query(sql, params)


@router.get("/wards/{ward_key}")
def ward_detail(ward_key: str, year: int = 2025, city_id: str = "bengaluru"):
    store = ToolResultStore()
    result = get_ward_metrics(store, city_id, ward_key, year)
    if result["data"] is None:
        raise HTTPException(status_code=404, detail=f"No ward '{ward_key}' for {city_id}/{year}")
    return result


@router.get("/risk")
def reweighted_risk(
    year: int = 2025,
    w_heat: float = 0.4,
    w_green: float = 0.2,
    w_built: float = 0.15,
    w_exposure: float = 0.25,
    city_id: str = "bengaluru",
):
    """Live re-ranking for the UI's weight sliders. Calls the
    ward_risk_reweighted table function built in pipeline/06_risk.sql,
    which only recombines already-computed percentile scores -- it never
    recomputes percentiles or touches rasters, so it's cheap per request."""
    weight_sum = w_heat + w_green + w_built + w_exposure
    if abs(weight_sum - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"weights must sum to 1.0 (got {weight_sum:.3f})")

    sql = f"""
    SELECT w.ward_key, w.ward_name, w.ward_name_kn, w.corporation,
      rr.composite_risk, rr.rank, rr.delta_lst_c
    FROM `{_T}.ward_risk_reweighted`(@year, @w_heat, @w_green, @w_built, @w_exposure) AS rr
    JOIN `{_T}.wards_clean` AS w ON w.ward_key = rr.ward_key
    WHERE w.city_id = @city_id
    ORDER BY rr.rank
    """
    params = [
        bigquery.ScalarQueryParameter("year", "INT64", year),
        bigquery.ScalarQueryParameter("w_heat", "FLOAT64", w_heat),
        bigquery.ScalarQueryParameter("w_green", "FLOAT64", w_green),
        bigquery.ScalarQueryParameter("w_built", "FLOAT64", w_built),
        bigquery.ScalarQueryParameter("w_exposure", "FLOAT64", w_exposure),
        bigquery.ScalarQueryParameter("city_id", "STRING", city_id),
    ]
    return run_query(sql, params)


@router.get("/sources/{tool_result_id}")
def get_source(tool_result_id: str):
    result = fetch_from_bigquery(tool_result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown tool_result_id")
    return result
