"""Intervention Planner: for a ward, pick applicable interventions from the
catalog and attach effect ranges (from effect_model, scaled to the actual
NDVI change each intervention implies) and citations.

Deliberately no eval() on applicability_rule -- it's a small, fixed set of
strings we wrote ourselves in cities/bengaluru.yaml, but a tiny regex
parser costs nothing and removes the whole class of risk.
"""

import re

from google.cloud import bigquery

from server.store import ToolResultStore
from server.tools.bq import DATASET, PROJECT, run_query

_T = f"{PROJECT}.{DATASET}"

_RULE_RE = re.compile(r"^(\w+)\s*(<=|>=|<|>|==)\s*([\d.]+)$")
_OPS = {
    "<": lambda a, b: a < b, ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
}


def _rule_applies(rule: str, metrics: dict) -> bool:
    rule = rule.strip()
    if rule == "true":
        return True
    m = _RULE_RE.match(rule)
    if not m:
        raise ValueError(f"unsupported applicability_rule: {rule!r}")
    field, op, value = m.group(1), m.group(2), float(m.group(3))
    actual = metrics.get(field)
    return actual is not None and _OPS[op](actual, value)


def _fetch_ward_metrics(city_id: str, ward_key: str, year: int) -> dict | None:
    sql = f"""
    SELECT w.ward_key, w.area_km2, m.ndvi_mean, m.built_frac
    FROM `{_T}.wards_clean` AS w
    JOIN `{_T}.ward_metrics` AS m ON m.ward_key = w.ward_key AND m.year = @year
    WHERE w.city_id = @city_id AND w.ward_key = @ward_key
    """
    rows = run_query(sql, [
        bigquery.ScalarQueryParameter("city_id", "STRING", city_id),
        bigquery.ScalarQueryParameter("ward_key", "STRING", ward_key),
        bigquery.ScalarQueryParameter("year", "INT64", year),
    ])
    return rows[0] if rows else None


def _fetch_catalog(city_id: str) -> list[dict]:
    sql = f"SELECT * FROM `{_T}.intervention_catalog` WHERE city_id = @city_id"
    return run_query(sql, [bigquery.ScalarQueryParameter("city_id", "STRING", city_id)])


def intervention_catalog(store: ToolResultStore, city_id: str) -> dict:
    """The catalog itself: every intervention's unit, assumed unit cost and
    citations, independent of any ward."""
    data = _fetch_catalog(city_id)
    return store.record("intervention_catalog", {"city_id": city_id}, data)


def _fetch_ndvi_effect_per_0_1() -> dict:
    sql = f"""
    SELECT effect_low_c, effect_mid_c, effect_high_c
    FROM `{_T}.effect_model`
    WHERE intervention = 'ndvi_increase_0.1' AND usable = TRUE
    """
    rows = run_query(sql)
    if not rows:
        raise RuntimeError("effect_model has no usable ndvi_increase_0.1 row -- run model/cooling_model.py")
    return rows[0]


def _ndvi_delta_for(catalog_row: dict, ward_area_km2: float) -> float:
    if catalog_row["ndvi_delta_per_unit"] is not None:
        return catalog_row["ndvi_delta_per_unit"]
    if catalog_row["ndvi_gain_in_treated_area"] is not None and catalog_row["treated_area_m2"] is not None:
        ward_area_m2 = ward_area_km2 * 1e6
        return (catalog_row["treated_area_m2"] * catalog_row["ndvi_gain_in_treated_area"]) / ward_area_m2
    return 0.0


def _build_recommendations(ward: dict, catalog: list[dict], ndvi_effect: dict) -> list[dict]:
    recommendations = []
    for row in catalog:
        if not _rule_applies(row["applicability_rule"], ward):
            continue

        rec = {
            "intervention_id": row["intervention_id"],
            "name": row["name"],
            "unit": row["unit"],
            "cost_inr_per_unit": row["cost_amount_inr_per_unit"],
            "cost_is_assumption": row["cost_is_assumption"],
            "cost_note": row["cost_note"],
            "citations": row["citations"],
        }

        if row["model_pathway_type"] == "modeled":
            ndvi_delta = _ndvi_delta_for(row, ward["area_km2"])
            scale = ndvi_delta / 0.1
            rec["effect_low_c"] = ndvi_effect["effect_low_c"] * scale
            rec["effect_mid_c"] = ndvi_effect["effect_mid_c"] * scale
            rec["effect_high_c"] = ndvi_effect["effect_high_c"] * scale
            rec["effect_type"] = "modeled_association"
        else:
            rec["effect_low_c"] = None
            rec["effect_mid_c"] = None
            rec["effect_high_c"] = None
            rec["effect_type"] = "not_quantified"
            rec["cited_fact"] = row["cited_fact_text"]

        recommendations.append(rec)
    return recommendations


def recommend_interventions(store: ToolResultStore, city_id: str, ward_key: str, year: int = 2025) -> dict:
    ward = _fetch_ward_metrics(city_id, ward_key, year)
    if ward is None:
        return store.record("recommend_interventions", {"city_id": city_id, "ward_key": ward_key, "year": year}, None)

    catalog = _fetch_catalog(city_id)
    ndvi_effect = _fetch_ndvi_effect_per_0_1()
    recommendations = _build_recommendations(ward, catalog, ndvi_effect)

    data = {"ward_key": ward_key, "ward_area_km2": ward["area_km2"], "recommendations": recommendations}
    return store.record("recommend_interventions", {"city_id": city_id, "ward_key": ward_key, "year": year}, data)


def _fetch_wards_in_scope(city_id: str, corporation: str | None, year: int) -> list[dict]:
    corp_filter = "AND w.corporation = @corporation" if corporation else ""
    sql = f"""
    SELECT w.ward_key, w.ward_name, w.corporation, w.area_km2,
      m.ndvi_mean, m.built_frac, p.population, r.rank
    FROM `{_T}.wards_clean` AS w
    JOIN `{_T}.ward_metrics` AS m ON m.ward_key = w.ward_key AND m.year = @year
    JOIN `{_T}.ward_population` AS p ON p.ward_key = w.ward_key
    JOIN `{_T}.ward_risk` AS r ON r.ward_key = w.ward_key AND r.year = @year
    WHERE w.city_id = @city_id {corp_filter}
    """
    params = [
        bigquery.ScalarQueryParameter("city_id", "STRING", city_id),
        bigquery.ScalarQueryParameter("year", "INT64", year),
    ]
    if corporation:
        params.append(bigquery.ScalarQueryParameter("corporation", "STRING", corporation))
    return run_query(sql, params)


def bulk_recommend_interventions(store: ToolResultStore, city_id: str, corporation: str | None = None, year: int = 2025) -> dict:
    """One SQL round-trip for every ward in scope, reusing the same
    applicability/effect-scaling logic as the single-ward tool -- for the
    budget optimizer, which needs every ward's options at once."""
    wards = _fetch_wards_in_scope(city_id, corporation, year)
    catalog = _fetch_catalog(city_id)
    ndvi_effect = _fetch_ndvi_effect_per_0_1()

    result_wards = []
    for ward in wards:
        result_wards.append({
            "ward_key": ward["ward_key"],
            "ward_name": ward["ward_name"],
            "corporation": ward["corporation"],
            "population": ward["population"],
            "rank": ward["rank"],
            "interventions": _build_recommendations(ward, catalog, ndvi_effect),
        })

    data = {"scope_corporation": corporation, "wards": result_wards}
    return store.record("bulk_recommend_interventions", {"city_id": city_id, "corporation": corporation, "year": year}, data)
