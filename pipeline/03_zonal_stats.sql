-- Phase 1, step 3: per-ward zonal statistics from the exported composites.
-- Run with: bq query --use_legacy_sql=false < pipeline/03_zonal_stats.sql
--
-- ST_REGIONSTATS verified live against gs://penumbra-509416-penumbra/rasters/
-- on 2026-09-24: returns a STRUCT with fields area, count, max, mean, min,
-- stdDev, sum. No percentile/quantile statistic exists, so the 90th
-- percentile of LST from CLAUDE.md step 3 is skipped (see docs/DECISIONS.md).
--
-- valid_pixel_frac uses the LST layer's returned `.area` (the true clipped
-- overlap area between valid pixels and the ward polygon) against the
-- ward's full area. An earlier version used `.count * 900`, assuming every
-- counted pixel contributes a full 900 sq m -- but `.count` counts any
-- pixel touching the ward at full weight, including boundary pixels only
-- partially inside it, which inflated every ward's fraction (up to 1.27,
-- i.e. impossible) for small/irregular wards. `.area` already accounts for
-- partial pixel overlap and is the correct field. See docs/DECISIONS.md.

CREATE OR REPLACE TABLE `penumbra-509416.penumbra.ward_metrics` AS
WITH stats_2016 AS (
  SELECT
    ward_key,
    area_km2,
    ST_REGIONSTATS(geometry, 'gs://penumbra-509416-penumbra/rasters/lst_2016.tif') AS lst,
    ST_REGIONSTATS(geometry, 'gs://penumbra-509416-penumbra/rasters/ndvi_2016.tif') AS ndvi,
    ST_REGIONSTATS(geometry, 'gs://penumbra-509416-penumbra/rasters/built_2016.tif') AS built
  FROM `penumbra-509416.penumbra.wards_clean`
),
stats_2025 AS (
  SELECT
    ward_key,
    area_km2,
    ST_REGIONSTATS(geometry, 'gs://penumbra-509416-penumbra/rasters/lst_2025.tif') AS lst,
    ST_REGIONSTATS(geometry, 'gs://penumbra-509416-penumbra/rasters/ndvi_2025.tif') AS ndvi,
    ST_REGIONSTATS(geometry, 'gs://penumbra-509416-penumbra/rasters/built_2025.tif') AS built
  FROM `penumbra-509416.penumbra.wards_clean`
),
combined AS (
  SELECT 'bengaluru' AS city_id, ward_key, 2016 AS year,
    lst.mean AS lst_mean_c, lst.max AS lst_max_c, ndvi.mean AS ndvi_mean,
    built.mean AS built_frac, lst.count AS valid_pixel_count,
    SAFE_DIVIDE(lst.area, area_km2 * 1e6) AS valid_pixel_frac
  FROM stats_2016
  UNION ALL
  SELECT 'bengaluru' AS city_id, ward_key, 2025 AS year,
    lst.mean AS lst_mean_c, lst.max AS lst_max_c, ndvi.mean AS ndvi_mean,
    built.mean AS built_frac, lst.count AS valid_pixel_count,
    SAFE_DIVIDE(lst.area, area_km2 * 1e6) AS valid_pixel_frac
  FROM stats_2025
)
SELECT * FROM combined;

-- ---------------------------------------------------------------------------
-- Sanity checks
-- ---------------------------------------------------------------------------

-- Expect 369 rows per year (738 total), no duplicate ward_key per year.
SELECT year, COUNT(*) AS n_wards, COUNT(DISTINCT ward_key) AS n_distinct_wards
FROM `penumbra-509416.penumbra.ward_metrics`
GROUP BY year
ORDER BY year;

-- Nulls: report any ward/year with a missing metric.
SELECT year,
  COUNTIF(lst_mean_c IS NULL) AS null_lst,
  COUNTIF(ndvi_mean IS NULL) AS null_ndvi,
  COUNTIF(built_frac IS NULL) AS null_built,
  COUNTIF(valid_pixel_frac IS NULL OR valid_pixel_frac < 0.5) AS low_coverage,
  COUNTIF(valid_pixel_frac > 1.02) AS impossible_over_one
FROM `penumbra-509416.penumbra.ward_metrics`
GROUP BY year
ORDER BY year;

-- Plausibility: LST and NDVI ranges per year.
SELECT year,
  ROUND(MIN(lst_mean_c), 1) AS lst_min, ROUND(AVG(lst_mean_c), 1) AS lst_avg, ROUND(MAX(lst_mean_c), 1) AS lst_max,
  ROUND(MIN(ndvi_mean), 2) AS ndvi_min, ROUND(AVG(ndvi_mean), 2) AS ndvi_avg, ROUND(MAX(ndvi_mean), 2) AS ndvi_max,
  ROUND(MIN(built_frac), 2) AS built_min, ROUND(AVG(built_frac), 2) AS built_avg, ROUND(MAX(built_frac), 2) AS built_max
FROM `penumbra-509416.penumbra.ward_metrics`
GROUP BY year
ORDER BY year;
