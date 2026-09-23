"""Phase 1, step 4: load OpenCity ward population data for the 2025 (369-ward)
delimitation and join it to wards_clean.

Verified 2026-09-24 (see docs/DECISIONS.md):
  - Resource: "GBA Final Wards Map With Population - Dec 2025", OpenCity CKAN
    dataset "gba-wards-delimitation-2025", license "Other (Public Domain)"
    (not ODbL as CLAUDE.md assumed -- see docs/DECISIONS.md).
  - It is a KML file with 369 placemarks. Its `id` field is the exact same
    key as our `wards_clean.ward_key` (e.g. "ward_369_final.33") -- it is
    the same source file our wards table was built from, with population
    columns added. All 369 ids match wards_clean exactly, so no fuzzy
    ward-number/corporation matching is needed.
  - Population figures (TOT_P etc.) are sourced from the 2011 Census,
    apportioned to the new 2025 ward boundaries -- not a fresh 2025 count.
    This must be stated in the product (data honesty rule).

Uses the `bq` CLI (already authenticated) instead of adding the
google-cloud-bigquery dependency for a one-off load. Loads via `bq query`
with a literal UNNEST array rather than `bq load`, since `bq load`'s
multipart file-upload path hit a persistent local SSL error
(SSLV3_ALERT_BAD_RECORD_MAC) in this environment, while `bq query` (used
throughout the rest of the pipeline) works reliably.

Run:
    source .venv/bin/activate
    python pipeline/04_population.py
"""

import re
import subprocess
import sys
import urllib.request

KML_URL = (
    "https://data.opencity.in/dataset/863209cb-4ced-4f51-b5c5-156939c50922"
    "/resource/9013d656-8051-4e2d-9648-46efd0d86d3d/download/"
    "gba-369-wards-december-2025.kml"
)
PROJECT = "penumbra-509416"
DATASET = "penumbra"
POPULATION_SOURCE_YEAR = 2011  # census vintage of TOT_P, per OpenCity notes


def fetch_kml() -> str:
    with urllib.request.urlopen(KML_URL) as resp:
        return resp.read().decode("utf-8")


def parse_placemarks(kml_text: str) -> list[dict]:
    rows = []
    for block in re.findall(r"<Placemark>.*?</Placemark>", kml_text, re.S):
        data = dict(re.findall(r'<SimpleData name="([^"]+)">([^<]*)</SimpleData>', block))
        rows.append(
            {
                "ward_key": data["id"],
                "population": round(float(data["TOT_P"])),
            }
        )
    return rows


def known_ward_keys() -> set[str]:
    out = subprocess.run(
        [
            "bq", "--quiet", "query", "--use_legacy_sql=false",
            "--max_rows=500", "--format=csv",
            f"SELECT ward_key FROM `{PROJECT}.{DATASET}.wards_clean`",
        ],
        capture_output=True, text=True, check=True,
    )
    lines = out.stdout.strip().splitlines()[1:]  # drop header
    return set(lines)


def main():
    print(f"Fetching {KML_URL} ...")
    rows = parse_placemarks(fetch_kml())
    print(f"Parsed {len(rows)} placemarks.")

    parsed_keys = {r["ward_key"] for r in rows}
    known_keys = known_ward_keys()
    missing_in_source = known_keys - parsed_keys
    missing_in_wards = parsed_keys - known_keys
    if missing_in_source or missing_in_wards:
        print("MISMATCH -- reporting, not guessing:")
        print("  wards_clean rows with no population row:", sorted(missing_in_source))
        print("  population rows with no matching ward:", sorted(missing_in_wards))
        sys.exit(1)
    print(f"All {len(rows)} wards matched 1:1 by ward_key. No fuzzy matching needed.")

    structs = ",\n".join(
        f"STRUCT('bengaluru' AS city_id, '{r['ward_key']}' AS ward_key, "
        f"{r['population']} AS population, {POPULATION_SOURCE_YEAR} AS population_source_year)"
        for r in rows
    )
    sql = (
        f"CREATE OR REPLACE TABLE `{PROJECT}.{DATASET}.ward_population` AS\n"
        f"SELECT * FROM UNNEST([\n{structs}\n])"
    )
    subprocess.run(
        ["bq", "--quiet", "query", "--use_legacy_sql=false", sql],
        check=True,
    )
    print(f"Loaded {len(rows)} rows into {PROJECT}.{DATASET}.ward_population.")


if __name__ == "__main__":
    main()
