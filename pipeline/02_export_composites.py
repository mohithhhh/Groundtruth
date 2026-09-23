"""Phase 1, step 2: export pre-monsoon composites (LST, NDVI, built fraction)
for the baseline year and 2025 as single-band Cloud Optimized GeoTIFFs.

Verified against the live Earth Engine catalog on 2026-09-24 (see
docs/DECISIONS.md):
  - LANDSAT/LC08/C02/T1_L2, LANDSAT/LC09/C02/T1_L2 (LC09 has no data before
    its 2021 launch, so 2016 uses LC08 only)
  - ST_B10: scale 0.00341802, offset 149 (Kelvin)
  - SR_B5 (NIR), SR_B4 (red): scale 2.75e-05, offset -0.2
  - QA_PIXEL bits 1/3/4 = dilated cloud / cloud / cloud shadow
  - GOOGLE/DYNAMICWORLD/V1 band 'built': coverage starts 2015-06-27, so the
    baseline year is 2016 (per CLAUDE.md's own rule: use 2016 if the chosen
    land-cover source starts mid-2015)

Cloud-cover check (Mar-May) over the ward bounding box: 2016 LC08 mean 6.5%
(0-22%), 2025 LC08+LC09 mean ~15% (0.3-72%). Both acceptable; no need to
widen to Jan-May.

Run:
    source .venv/bin/activate
    python pipeline/02_export_composites.py

This only *starts* Earth Engine export tasks (async, run server-side) and
prints their task IDs. Check progress with `earthengine task list` or the
Earth Engine Tasks tab.
"""

import ee
import google.auth

PROJECT = "penumbra-509416"
BUCKET = "penumbra-509416-penumbra"
SCALE_M = 30
CRS = "EPSG:32643"  # UTM 43N, matches Landsat's native resolution for Bengaluru

_creds, _ = google.auth.default(
    scopes=[
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/earthengine",
    ]
)
ee.Initialize(credentials=_creds, project=PROJECT)

# Bounding box of all 369 wards + 1km buffer, from wards_clean via:
#   SELECT ST_BOUNDINGBOX(ST_BUFFER(ST_UNION_AGG(geometry), 1000))
#   FROM `penumbra-509416.penumbra.wards_clean`
# Run 2026-09-24.
REGION = ee.Geometry.Rectangle(
    [77.45066665638006, 12.82452311827992, 77.79329079680647, 13.151590889081893]
)

BASELINE_YEAR = 2016
TARGET_YEAR = 2025
SEASON = ("03-01", "05-31")  # pre-monsoon

CLOUD_BIT, SHADOW_BIT, DILATED_CLOUD_BIT = 3, 4, 1


def mask_landsat(img):
    qa = img.select("QA_PIXEL")
    mask = (
        qa.bitwiseAnd(1 << CLOUD_BIT)
        .eq(0)
        .And(qa.bitwiseAnd(1 << SHADOW_BIT).eq(0))
        .And(qa.bitwiseAnd(1 << DILATED_CLOUD_BIT).eq(0))
    )
    return img.updateMask(mask)


def landsat_collection(year):
    date_range = (f"{year}-{SEASON[0]}", f"{year}-{SEASON[1]}")
    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterDate(*date_range)
    l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2").filterDate(*date_range)
    return (
        l8.merge(l9)
        .filterBounds(REGION)
        .map(mask_landsat)
    )


def lst_celsius(img):
    return (
        img.select("ST_B10")
        .multiply(0.00341802)
        .add(149.0)
        .subtract(273.15)
        .rename("lst_c")
    )


def ndvi(img):
    nir = img.select("SR_B5").multiply(2.75e-05).add(-0.2)
    red = img.select("SR_B4").multiply(2.75e-05).add(-0.2)
    return nir.subtract(red).divide(nir.add(red)).rename("ndvi")


def composites_for_year(year):
    col = landsat_collection(year)
    lst = col.map(lst_celsius).median().clip(REGION)
    ndvi_img = col.map(ndvi).median().clip(REGION)
    built = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterDate(f"{year}-{SEASON[0]}", f"{year}-{SEASON[1]}")
        .filterBounds(REGION)
        .select("built")
        .median()
        .clip(REGION)
        .rename("built_frac")
    )
    return {"lst": lst, "ndvi": ndvi_img, "built": built}


def export(image, layer, year):
    task = ee.batch.Export.image.toCloudStorage(
        image=image,
        description=f"{layer}_{year}",
        bucket=BUCKET,
        fileNamePrefix=f"rasters/{layer}_{year}",
        region=REGION,
        scale=SCALE_M,
        crs=CRS,
        maxPixels=1e10,
        fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": True},
    )
    task.start()
    return task


def main():
    tasks = []
    for year in (BASELINE_YEAR, TARGET_YEAR):
        layers = composites_for_year(year)
        for layer_name, image in layers.items():
            task = export(image, layer_name, year)
            tasks.append((layer_name, year, task.id))
            print(f"started: {layer_name}_{year} -> task {task.id}")

    print("\nAll export tasks started. Track with `earthengine task list`.")
    return tasks


if __name__ == "__main__":
    main()
