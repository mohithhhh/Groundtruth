"""Phase 1, step 8: export simplified ward polygons to web/public/data/wards.geojson.

Uses `bq query` (proven reliable in this environment; see docs/DECISIONS.md
re: bq load's SSL issue) to get ST_ASGEOJSON per ward, then assembles a
FeatureCollection with stdlib json -- no geopandas/shapely needed for a
369-feature file.

Run:
    python pipeline/08_export_geojson.py
"""

import json
import subprocess

PROJECT = "penumbra-509416"
DATASET = "penumbra"
SIMPLIFY_TOLERANCE_M = 15
OUT_PATH = "web/public/data/wards.geojson"
MAX_BYTES = 1_500_000


def fetch_wards():
    sql = f"""
    SELECT
      ward_key, ward_no, ward_name, ward_name_kn, corporation,
      ST_ASGEOJSON(ST_SIMPLIFY(geometry, {SIMPLIFY_TOLERANCE_M})) AS geometry_json
    FROM `{PROJECT}.{DATASET}.wards_clean`
    ORDER BY ward_key
    """
    out = subprocess.run(
        ["bq", "--quiet", "query", "--use_legacy_sql=false", "--max_rows=500", "--format=json", sql],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def main():
    rows = fetch_wards()
    features = [
        {
            "type": "Feature",
            "geometry": json.loads(r["geometry_json"]),
            "properties": {
                "ward_key": r["ward_key"],
                "ward_no": int(r["ward_no"]),
                "ward_name": r["ward_name"],
                "ward_name_kn": r["ward_name_kn"],
                "corporation": r["corporation"],
            },
        }
        for r in rows
    ]
    fc = {"type": "FeatureCollection", "features": features}

    import os
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(OUT_PATH)
    print(f"Wrote {len(features)} features to {OUT_PATH} ({size:,} bytes).")
    if size > MAX_BYTES:
        print(f"WARNING: exceeds the {MAX_BYTES:,} byte target -- consider a larger simplify tolerance.")


if __name__ == "__main__":
    main()
