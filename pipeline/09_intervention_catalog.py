"""Phase 3, step 2: load cities/bengaluru.yaml into BigQuery
intervention_catalog and guidance_documents tables.

Run:
    source .venv/bin/activate
    python pipeline/09_intervention_catalog.py
"""

import subprocess

import yaml

PROJECT = "penumbra-509416"
DATASET = "penumbra"
CITY_YAML = "cities/bengaluru.yaml"


def sql_str(s: str) -> str:
    return s.replace("'", "\\'")


def build_guidance_documents_sql(city: dict) -> str:
    structs = ",\n".join(
        f"STRUCT('{city['city_id']}' AS city_id, '{d['id']}' AS doc_id, "
        f"'{sql_str(d['title'])}' AS title, '{d['publisher']}' AS publisher, "
        f"'{d['url']}' AS url, '{d['date']}' AS doc_date)"
        for d in city["guidance_documents"]
    )
    return (
        f"CREATE OR REPLACE TABLE `{PROJECT}.{DATASET}.guidance_documents` AS\n"
        f"SELECT * FROM UNNEST([\n{structs}\n])"
    )


def build_intervention_catalog_sql(city: dict) -> str:
    rows = []
    for iv in city["interventions"]:
        pathway = iv["model_pathway"]
        cost = iv["cost"]
        cited_fact = iv.get("cited_fact")
        citations = ",\n      ".join(
            f"STRUCT('{c['id']}' AS doc_id, {c['page']} AS page, '{sql_str(c['quote'])}' AS quote)"
            for c in iv["citations"]
        )
        cited_fact_sql = "CAST(NULL AS STRING)" if cited_fact is None else f"'{sql_str(cited_fact['text'])}'"
        ndvi_delta_sql = f"CAST({pathway['ndvi_delta_per_unit']} AS FLOAT64)" if "ndvi_delta_per_unit" in pathway else "CAST(NULL AS FLOAT64)"
        ndvi_gain_sql = f"CAST({pathway['ndvi_gain_in_treated_area']} AS FLOAT64)" if "ndvi_gain_in_treated_area" in pathway else "CAST(NULL AS FLOAT64)"
        treated_area_sql = f"CAST({pathway['treated_area_m2']} AS INT64)" if "treated_area_m2" in pathway else "CAST(NULL AS INT64)"
        rows.append(
            "STRUCT(\n"
            f"  '{city['city_id']}' AS city_id,\n"
            f"  '{iv['id']}' AS intervention_id,\n"
            f"  '{sql_str(iv['name'])}' AS name,\n"
            f"  '{sql_str(iv['unit'])}' AS unit,\n"
            f"  '{sql_str(iv['applicability_rule'])}' AS applicability_rule,\n"
            f"  '{pathway['type']}' AS model_pathway_type,\n"
            f"  '{sql_str(pathway['description'])}' AS model_pathway_description,\n"
            f"  {ndvi_delta_sql} AS ndvi_delta_per_unit,\n"
            f"  {ndvi_gain_sql} AS ndvi_gain_in_treated_area,\n"
            f"  {treated_area_sql} AS treated_area_m2,\n"
            f"  {cited_fact_sql} AS cited_fact_text,\n"
            f"  CAST({cost['amount_inr_per_unit']} AS INT64) AS cost_amount_inr_per_unit,\n"
            f"  {'TRUE' if cost['assumption'] else 'FALSE'} AS cost_is_assumption,\n"
            f"  '{sql_str(cost['note'])}' AS cost_note,\n"
            f"  [\n      {citations}\n  ] AS citations\n"
            ")"
        )
    structs = ",\n".join(rows)
    return (
        f"CREATE OR REPLACE TABLE `{PROJECT}.{DATASET}.intervention_catalog` AS\n"
        f"SELECT * FROM UNNEST([\n{structs}\n])"
    )


def main():
    with open(CITY_YAML) as f:
        city = yaml.safe_load(f)

    subprocess.run(["bq", "--quiet", "query", "--use_legacy_sql=false", build_guidance_documents_sql(city)], check=True)
    print(f"Loaded guidance_documents ({len(city['guidance_documents'])} rows)")

    subprocess.run(["bq", "--quiet", "query", "--use_legacy_sql=false", build_intervention_catalog_sql(city)], check=True)
    print(f"Loaded intervention_catalog ({len(city['interventions'])} rows)")


if __name__ == "__main__":
    main()
