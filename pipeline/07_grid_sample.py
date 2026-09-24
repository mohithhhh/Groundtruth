"""Phase 3, step 1: sample a 150m grid across the city with LST, NDVI,
built fraction, elevation and distance to water, for fitting the
cooling-effect model in model/cooling_model.py.

Verified 2026-09-25 (see docs/DECISIONS.md):
  - Elevation: USGS/SRTMGL1_003, already tested in CLAUDE.md (886-908m for
    real wards).
  - Water: reused GOOGLE/DYNAMICWORLD/V1 band 'water' (already verified and
    used for built fraction in 02_export_composites.py) instead of sourcing
    a separate water dataset -- same collection, same coverage, one less
    thing to verify.
  - ee.Image.distance(kernel) computes distance to the nearest non-zero
    pixel; ee.Kernel.euclidean(radius, 'meters') gives that distance in
    meters. Confirmed directly from the installed `ee` package's docstrings,
    not just docs.

Run:
    source .venv/bin/activate
    python pipeline/07_grid_sample.py
"""

import subprocess
import sys
import time

import ee

sys.path.insert(0, "pipeline")
from importlib import import_module

_export_composites = import_module("02_export_composites")

BUCKET = "penumbra-509416-penumbra"
GRID_SPACING_M = 150
WATER_PROBABILITY_THRESHOLD = 0.5
MAX_DISTANCE_M = 5000
EXPORT_PREFIX = "model/grid_sample_2025"
LOCAL_CSV_PATH = "model/grid_sample_2025.csv"


def build_covariate_image() -> ee.Image:
    year = _export_composites.TARGET_YEAR  # 2025
    layers = _export_composites.composites_for_year(year)

    elevation = ee.Image("USGS/SRTMGL1_003").select("elevation").clip(_export_composites.REGION)

    water_prob = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterDate(f"{year}-{_export_composites.SEASON[0]}", f"{year}-{_export_composites.SEASON[1]}")
        .filterBounds(_export_composites.REGION)
        .select("water")
        .median()
    )
    water_mask = water_prob.gte(WATER_PROBABILITY_THRESHOLD)
    dist_to_water = (
        water_mask.distance(ee.Kernel.euclidean(MAX_DISTANCE_M, "meters"))
        .clip(_export_composites.REGION)
        .rename("dist_water_m")
    )

    return (
        layers["lst"].rename("lst_c")
        .addBands(layers["ndvi"].rename("ndvi"))
        .addBands(layers["built"].rename("built_frac"))
        .addBands(elevation.rename("elevation_m"))
        .addBands(dist_to_water)
    )


def start_export(image: ee.Image) -> ee.batch.Task:
    grid = image.sample(
        region=_export_composites.REGION,
        scale=GRID_SPACING_M,
        projection=_export_composites.CRS,
        geometries=True,
        dropNulls=True,
    )
    grid = grid.map(lambda f: f.set({
        "lon": f.geometry().coordinates().get(0),
        "lat": f.geometry().coordinates().get(1),
    }))
    task = ee.batch.Export.table.toCloudStorage(
        collection=grid,
        description="grid_sample_2025",
        bucket=BUCKET,
        fileNamePrefix=EXPORT_PREFIX,
        fileFormat="CSV",
    )
    task.start()
    return task


def wait_for_task(task: ee.batch.Task, poll_seconds: int = 15) -> None:
    while True:
        status = task.status()
        state = status["state"]
        print(f"  task state: {state}")
        if state in ("COMPLETED", "FAILED", "CANCELLED"):
            if state != "COMPLETED":
                raise RuntimeError(f"export task ended in state {state}: {status}")
            return
        time.sleep(poll_seconds)


def main():
    _export_composites  # already ran ee.Initialize() at import time

    print("Building covariate image (LST, NDVI, built, elevation, dist_water)...")
    image = build_covariate_image()

    print(f"Starting grid sample export ({GRID_SPACING_M}m spacing)...")
    task = start_export(image)
    print(f"  task id: {task.id}")
    wait_for_task(task)

    print("Downloading exported CSV...")
    subprocess.run(
        ["gcloud", "storage", "cp", f"gs://{BUCKET}/{EXPORT_PREFIX}.csv", LOCAL_CSV_PATH],
        check=True,
    )
    print(f"Saved to {LOCAL_CSV_PATH}")


if __name__ == "__main__":
    main()
