"""Phase 1, step 8 (extended in Phase 4): export simplified ward polygons and
dissolved corporation boundaries for the web map.

Outputs:
  web/public/data/wards.geojson        369 ward polygons + centroid for labels
  web/public/data/corporations.geojson 5 corporation boundaries (for the
                                       1.5px corporation border layer)

Centroids are carried as properties because the map draws ward labels as
HTML in Hanken Grotesk rather than MapLibre symbol layers, which would need
a third-party glyph server (CLAUDE.md: no third-party tiles by default).

Uses `bq query` (proven reliable in this environment; see docs/DECISIONS.md
re: bq load's SSL issue). Coordinates are rounded to 5 decimals (~1 m),
well below the 15 m simplification tolerance.

Run:
    python pipeline/08_export_geojson.py
"""

import json
import os
import subprocess

PROJECT = "penumbra-509416"
DATASET = "penumbra"
SIMPLIFY_TOLERANCE_M = 15
WARDS_OUT = "web/public/data/wards.geojson"
CORPS_OUT = "web/public/data/corporations.geojson"
MAX_BYTES = 1_500_000


def bq_json(sql: str) -> list[dict]:
    out = subprocess.run(
        ["bq", "--quiet", "query", "--use_legacy_sql=false", "--max_rows=500", "--format=json", sql],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def round_coords(obj):
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return [round(v, 5) for v in obj]
        return [round_coords(v) for v in obj]
    return obj


def _polygons(g: dict) -> list:
    """Polygon rings from any geometry. ST_SIMPLIFY leaves some wards as a
    GeometryCollection of the polygon plus zero-area line/point slivers;
    only the polygon parts are real area, so the slivers are dropped."""
    if g["type"] == "Polygon":
        return [g["coordinates"]]
    if g["type"] == "MultiPolygon":
        return g["coordinates"]
    if g["type"] == "GeometryCollection":
        return [p for part in g["geometries"] for p in _polygons(part)]
    return []


def geometry(geojson_str: str) -> dict:
    polys = round_coords(_polygons(json.loads(geojson_str)))
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


def write(path: str, features: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(path)
    print(f"Wrote {len(features)} features to {path} ({size:,} bytes).")
    if size > MAX_BYTES:
        print(f"WARNING: exceeds the {MAX_BYTES:,} byte target -- consider a larger simplify tolerance.")


def main():
    wards = bq_json(f"""
    SELECT
      ward_key, ward_no, ward_name, ward_name_kn, corporation,
      ST_X(centroid) AS centroid_lon, ST_Y(centroid) AS centroid_lat, area_km2,
      ST_ASGEOJSON(ST_SIMPLIFY(geometry, {SIMPLIFY_TOLERANCE_M})) AS geometry_json
    FROM `{PROJECT}.{DATASET}.wards_clean`
    ORDER BY ward_key
    """)
    write(WARDS_OUT, [
        {
            "type": "Feature",
            "geometry": geometry(r["geometry_json"]),
            "properties": {
                "ward_key": r["ward_key"],
                "ward_no": int(r["ward_no"]),
                "ward_name": r["ward_name"],
                "ward_name_kn": r["ward_name_kn"],
                "corporation": r["corporation"],
                "centroid": [round(float(r["centroid_lon"]), 5), round(float(r["centroid_lat"]), 5)],
                "area_km2": round(float(r["area_km2"]), 3),
            },
        }
        for r in wards
    ])

    corps = bq_json(f"""
    SELECT corporation,
      ST_ASGEOJSON(ST_SIMPLIFY(ST_UNION_AGG(geometry), {SIMPLIFY_TOLERANCE_M * 2})) AS geometry_json
    FROM `{PROJECT}.{DATASET}.wards_clean`
    GROUP BY corporation
    ORDER BY corporation
    """)
    write(CORPS_OUT, [
        {"type": "Feature", "geometry": geometry(r["geometry_json"]), "properties": {"corporation": r["corporation"]}}
        for r in corps
    ])


if __name__ == "__main__":
    main()
