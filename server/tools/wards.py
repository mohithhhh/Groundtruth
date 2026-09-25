"""Read-only, parameterized-SQL tools over the Phase 1 tables. Every
function returns {tool_result_id, data} via the caller's ToolResultStore --
the LLM never sees raw SQL results without a citable id attached to them.
"""

from google.cloud import bigquery

from server.store import ToolResultStore
from server.tools.bq import DATASET, PROJECT, run_query

_T = f"{PROJECT}.{DATASET}"

# The baseline year delta_lst_c is measured from (pipeline/06_risk.sql).
BASELINE_YEAR = 2016

# Allow-list: metric name -> (table, column, has_year). No free-form SQL from
# the model -- rank_wards and compare_years can only touch these.
_METRIC_COLUMNS = {
    "lst_mean_c": ("ward_metrics", "lst_mean_c", True),
    "lst_max_c": ("ward_metrics", "lst_max_c", True),
    "ndvi_mean": ("ward_metrics", "ndvi_mean", True),
    "built_frac": ("ward_metrics", "built_frac", True),
    "valid_pixel_frac": ("ward_metrics", "valid_pixel_frac", True),
    "composite_risk": ("ward_risk", "composite_risk", True),
    "delta_lst_c": ("ward_risk", "delta_lst_c", True),
    "population": ("ward_population", "population", False),
}


def get_ward_metrics(store: ToolResultStore, city_id: str, ward_key: str, year: int) -> dict:
    sql = f"""
    SELECT
      w.ward_key, w.ward_no, w.ward_name, w.ward_name_kn, w.corporation, w.ac, w.area_km2,
      m.lst_mean_c, m.lst_max_c, m.ndvi_mean, m.built_frac, m.valid_pixel_frac,
      p.population, p.population_source_year,
      r.composite_risk, r.rank, r.delta_lst_c
    FROM `{_T}.wards_clean` AS w
    JOIN `{_T}.ward_metrics` AS m ON m.ward_key = w.ward_key AND m.year = @year
    LEFT JOIN `{_T}.ward_population` AS p ON p.ward_key = w.ward_key
    LEFT JOIN `{_T}.ward_risk` AS r ON r.ward_key = w.ward_key AND r.year = @year
    WHERE w.city_id = @city_id AND w.ward_key = @ward_key
    """
    params = [
        bigquery.ScalarQueryParameter("city_id", "STRING", city_id),
        bigquery.ScalarQueryParameter("ward_key", "STRING", ward_key),
        bigquery.ScalarQueryParameter("year", "INT64", year),
    ]
    rows = run_query(sql, params)
    data = rows[0] if rows else None
    return store.record("get_ward_metrics", {"city_id": city_id, "ward_key": ward_key, "year": year}, data)


def find_ward(store: ToolResultStore, city_id: str, name_query: str, limit: int = 5) -> dict:
    """Fuzzy match on English and Kannada names. Returns ranked candidates --
    never silently picks one, per CLAUDE.md."""
    sql = f"""
    SELECT ward_key, ward_name, ward_name_kn, corporation,
      LEAST(EDIT_DISTANCE(LOWER(ward_name), LOWER(@q)), EDIT_DISTANCE(ward_name_kn, @q)) AS distance
    FROM `{_T}.wards_clean`
    WHERE city_id = @city_id
    ORDER BY distance ASC
    LIMIT @limit
    """
    params = [
        bigquery.ScalarQueryParameter("city_id", "STRING", city_id),
        bigquery.ScalarQueryParameter("q", "STRING", name_query),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    data = run_query(sql, params)
    return store.record("find_ward", {"city_id": city_id, "name_query": name_query, "limit": limit}, data)


def rank_wards(
    store: ToolResultStore, city_id: str, metric: str, n: int, year: int,
    corporation: str | None = None, order: str = "desc",
) -> dict:
    if metric not in _METRIC_COLUMNS:
        raise ValueError(f"metric must be one of {sorted(_METRIC_COLUMNS)}")
    if order not in ("asc", "desc"):
        raise ValueError("order must be 'asc' or 'desc'")
    table, column, has_year = _METRIC_COLUMNS[metric]

    year_join = f"AND t.year = @year" if has_year else ""
    # A change ranking also returns its baseline year, so an answer can cite
    # "since 2016" to a tool result like any other figure.
    baseline = f", {BASELINE_YEAR} AS baseline_year" if metric == "delta_lst_c" else ""
    corp_filter = "AND w.corporation = @corporation" if corporation else ""
    sql = f"""
    SELECT w.ward_key, w.ward_name, w.ward_name_kn, w.corporation, t.{column} AS value{baseline}
    FROM `{_T}.wards_clean` AS w
    JOIN `{_T}.{table}` AS t ON t.ward_key = w.ward_key {year_join}
    WHERE w.city_id = @city_id {corp_filter}
    ORDER BY value {order.upper()}
    LIMIT @n
    """
    params = [
        bigquery.ScalarQueryParameter("city_id", "STRING", city_id),
        bigquery.ScalarQueryParameter("n", "INT64", n),
    ]
    if has_year:
        params.append(bigquery.ScalarQueryParameter("year", "INT64", year))
    if corporation:
        params.append(bigquery.ScalarQueryParameter("corporation", "STRING", corporation))
    data = run_query(sql, params)
    return store.record(
        "rank_wards",
        {"city_id": city_id, "metric": metric, "n": n, "year": year, "corporation": corporation, "order": order},
        data,
    )


def compare_years(store: ToolResultStore, city_id: str, ward_keys: list[str], metric: str, year_a: int, year_b: int) -> dict:
    if metric not in _METRIC_COLUMNS:
        raise ValueError(f"metric must be one of {sorted(_METRIC_COLUMNS)}")
    table, column, has_year = _METRIC_COLUMNS[metric]
    if not has_year:
        raise ValueError(f"{metric} has no per-year values to compare")
    sql = f"""
    SELECT w.ward_key, w.ward_name,
      a.{column} AS value_a, b.{column} AS value_b, b.{column} - a.{column} AS change
    FROM `{_T}.wards_clean` AS w
    JOIN `{_T}.{table}` AS a ON a.ward_key = w.ward_key AND a.year = @year_a
    JOIN `{_T}.{table}` AS b ON b.ward_key = w.ward_key AND b.year = @year_b
    WHERE w.city_id = @city_id AND w.ward_key IN UNNEST(@ward_keys)
    """
    params = [
        bigquery.ScalarQueryParameter("city_id", "STRING", city_id),
        bigquery.ArrayQueryParameter("ward_keys", "STRING", ward_keys),
        bigquery.ScalarQueryParameter("year_a", "INT64", year_a),
        bigquery.ScalarQueryParameter("year_b", "INT64", year_b),
    ]
    data = run_query(sql, params)
    return store.record(
        "compare_years",
        {"city_id": city_id, "ward_keys": ward_keys, "metric": metric, "year_a": year_a, "year_b": year_b},
        data,
    )


def corporation_summary(store: ToolResultStore, city_id: str, corporation: str, year: int) -> dict:
    sql = f"""
    SELECT
      w.corporation,
      COUNT(*) AS ward_count,
      AVG(m.lst_mean_c) AS avg_lst_c,
      AVG(m.ndvi_mean) AS avg_ndvi,
      AVG(m.built_frac) AS avg_built_frac,
      AVG(r.composite_risk) AS avg_composite_risk,
      SUM(p.population) AS total_population
    FROM `{_T}.wards_clean` AS w
    JOIN `{_T}.ward_metrics` AS m ON m.ward_key = w.ward_key AND m.year = @year
    LEFT JOIN `{_T}.ward_risk` AS r ON r.ward_key = w.ward_key AND r.year = @year
    LEFT JOIN `{_T}.ward_population` AS p ON p.ward_key = w.ward_key
    WHERE w.city_id = @city_id AND w.corporation = @corporation
    GROUP BY w.corporation
    """
    params = [
        bigquery.ScalarQueryParameter("city_id", "STRING", city_id),
        bigquery.ScalarQueryParameter("corporation", "STRING", corporation),
        bigquery.ScalarQueryParameter("year", "INT64", year),
    ]
    rows = run_query(sql, params)
    data = rows[0] if rows else None
    return store.record("corporation_summary", {"city_id": city_id, "corporation": corporation, "year": year}, data)


def nearby_facilities(store: ToolResultStore, city_id: str, ward_key: str, type: str | None = None) -> dict:
    if type is not None and type not in ("hospital", "school"):
        raise ValueError("type must be 'hospital', 'school', or None")
    type_filter = "AND i.type = @type" if type else ""
    sql = f"""
    SELECT i.type, i.name, i.category
    FROM `{_T}.infra_points` AS i
    WHERE i.city_id = @city_id AND i.ward_key = @ward_key {type_filter}
    ORDER BY i.type, i.name
    """
    params = [
        bigquery.ScalarQueryParameter("city_id", "STRING", city_id),
        bigquery.ScalarQueryParameter("ward_key", "STRING", ward_key),
    ]
    if type:
        params.append(bigquery.ScalarQueryParameter("type", "STRING", type))
    rows = run_query(sql, params)
    counts = {"hospital": 0, "school": 0}
    for r in rows:
        counts[r["type"]] += 1
    data = {"counts": counts, "facilities": rows}
    return store.record("nearby_facilities", {"city_id": city_id, "ward_key": ward_key, "type": type}, data)


_RASTER_BUCKET = "gs://penumbra-509416-penumbra/rasters"
_LIVE_LAYERS = {"lst", "ndvi", "built"}
_LIVE_YEARS = {2016, 2025}


def live_regionstats(store: ToolResultStore, ward_key: str, layer: str, year: int) -> dict:
    """The one call in the app that recomputes a figure live from the
    exported Earth Engine raster via BigQuery's ST_REGIONSTATS, rather than
    reading the precomputed ward_metrics table -- for the demo. layer and
    year are checked against a small allow-list before being used to build
    the gs:// URI, so this stays a fixed, non-arbitrary set of raster
    files, consistent with "no free-form SQL from the model."""
    if layer not in _LIVE_LAYERS:
        raise ValueError(f"layer must be one of {sorted(_LIVE_LAYERS)}")
    if year not in _LIVE_YEARS:
        raise ValueError(f"year must be one of {sorted(_LIVE_YEARS)}")
    raster_uri = f"{_RASTER_BUCKET}/{layer}_{year}.tif"
    sql = f"""
    SELECT ST_REGIONSTATS(geometry, @raster_uri) AS stats
    FROM `{_T}.wards_clean`
    WHERE ward_key = @ward_key
    """
    params = [
        bigquery.ScalarQueryParameter("raster_uri", "STRING", raster_uri),
        bigquery.ScalarQueryParameter("ward_key", "STRING", ward_key),
    ]
    rows = run_query(sql, params)
    data = rows[0]["stats"] if rows else None
    return store.record("live_regionstats", {"ward_key": ward_key, "layer": layer, "year": year}, data)


def compare_to_city_median(store: ToolResultStore, city_id: str, ward_key: str, year: int) -> dict:
    """The ward's surface temperature against the citywide median of ward
    means for the same year -- the difference is computed in SQL so the
    ward sheet's hero figure is a traceable tool result, not browser math."""
    sql = f"""
    WITH city AS (
      SELECT APPROX_QUANTILES(m.lst_mean_c, 100)[OFFSET(50)] AS city_median_lst_c
      FROM `{_T}.ward_metrics` AS m
      JOIN `{_T}.wards_clean` AS w USING (ward_key)
      WHERE w.city_id = @city_id AND m.year = @year
    )
    SELECT m.ward_key, m.lst_mean_c, city.city_median_lst_c,
      m.lst_mean_c - city.city_median_lst_c AS difference_c
    FROM `{_T}.ward_metrics` AS m, city
    WHERE m.ward_key = @ward_key AND m.year = @year
    """
    rows = run_query(sql, [
        bigquery.ScalarQueryParameter("city_id", "STRING", city_id),
        bigquery.ScalarQueryParameter("ward_key", "STRING", ward_key),
        bigquery.ScalarQueryParameter("year", "INT64", year),
    ])
    data = rows[0] if rows else None
    return store.record("compare_to_city_median", {"city_id": city_id, "ward_key": ward_key, "year": year}, data)
