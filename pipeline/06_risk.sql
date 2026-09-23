-- Phase 1, step 6: composite heat-risk score per ward and year.
-- Run with: bq query --use_legacy_sql=false < pipeline/06_risk.sql
--
-- Percentile-rank components (heat_score, green_deficit, built_pressure,
-- exposure_score) are computed once and stored, so the reweighting table
-- function below only needs to combine them -- it never recomputes ranks.
--
-- population is a single 2011-census-derived snapshot apportioned to the
-- 2025 wards (see docs/DECISIONS.md) -- there is no separate baseline-year
-- population, so exposure_score is identical for both years by construction.
--
-- delta_lst_c is relative to the baseline year: 0 for baseline-year rows,
-- (this year's LST - baseline LST) for 2025 rows.

CREATE OR REPLACE TABLE `penumbra-509416.penumbra.ward_risk` AS
WITH density AS (
  SELECT
    w.ward_key,
    SAFE_DIVIDE(p.population, w.area_km2) AS pop_density
  FROM `penumbra-509416.penumbra.wards_clean` AS w
  JOIN `penumbra-509416.penumbra.ward_population` AS p USING (ward_key)
),
baseline AS (
  SELECT ward_key, lst_mean_c AS baseline_lst_c
  FROM `penumbra-509416.penumbra.ward_metrics`
  WHERE year = 2016
),
scored AS (
  SELECT
    m.city_id,
    m.ward_key,
    m.year,
    m.lst_mean_c,
    m.ndvi_mean,
    m.built_frac,
    d.pop_density,
    PERCENT_RANK() OVER (PARTITION BY m.year ORDER BY m.lst_mean_c) AS heat_score,
    1 - PERCENT_RANK() OVER (PARTITION BY m.year ORDER BY m.ndvi_mean) AS green_deficit,
    PERCENT_RANK() OVER (PARTITION BY m.year ORDER BY m.built_frac) AS built_pressure,
    PERCENT_RANK() OVER (PARTITION BY m.year ORDER BY d.pop_density) AS exposure_score,
    m.lst_mean_c - b.baseline_lst_c AS delta_lst_c
  FROM `penumbra-509416.penumbra.ward_metrics` AS m
  JOIN density AS d USING (ward_key)
  JOIN baseline AS b USING (ward_key)
)
SELECT
  city_id,
  ward_key,
  year,
  heat_score,
  green_deficit,
  built_pressure,
  exposure_score,
  0.4 * heat_score + 0.2 * green_deficit + 0.15 * built_pressure + 0.25 * exposure_score AS composite_risk,
  0.4 AS weight_heat,
  0.2 AS weight_green,
  0.15 AS weight_built,
  0.25 AS weight_exposure,
  RANK() OVER (PARTITION BY year ORDER BY 0.4 * heat_score + 0.2 * green_deficit + 0.15 * built_pressure + 0.25 * exposure_score DESC) AS rank,
  delta_lst_c
FROM scored;

-- ---------------------------------------------------------------------------
-- Reweighting table function for the UI sliders. Recomputes composite_risk
-- and rank from the already-stored percentile components -- does not touch
-- rasters or recompute percentiles, so it is cheap enough to call per request.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE FUNCTION `penumbra-509416.penumbra.ward_risk_reweighted`(
  target_year INT64, w_heat FLOAT64, w_green FLOAT64, w_built FLOAT64, w_exposure FLOAT64
) AS (
  SELECT
    city_id,
    ward_key,
    year,
    heat_score,
    green_deficit,
    built_pressure,
    exposure_score,
    w_heat * heat_score + w_green * green_deficit + w_built * built_pressure + w_exposure * exposure_score AS composite_risk,
    RANK() OVER (
      ORDER BY w_heat * heat_score + w_green * green_deficit + w_built * built_pressure + w_exposure * exposure_score DESC
    ) AS rank,
    delta_lst_c
  FROM `penumbra-509416.penumbra.ward_risk`
  WHERE year = target_year
);

-- ---------------------------------------------------------------------------
-- Sanity checks
-- ---------------------------------------------------------------------------

-- Grain and null check.
SELECT year, COUNT(*) AS n, COUNTIF(composite_risk IS NULL) AS null_composite
FROM `penumbra-509416.penumbra.ward_risk`
GROUP BY year
ORDER BY year;

-- Top 10 highest-risk wards for 2025, with their raw metrics for a sanity read.
SELECT r.rank, w.ward_name, w.corporation, m.lst_mean_c, m.ndvi_mean, m.built_frac, r.composite_risk, r.delta_lst_c
FROM `penumbra-509416.penumbra.ward_risk` AS r
JOIN `penumbra-509416.penumbra.wards_clean` AS w USING (ward_key)
JOIN `penumbra-509416.penumbra.ward_metrics` AS m ON m.ward_key = r.ward_key AND m.year = r.year
WHERE r.year = 2025
ORDER BY r.rank
LIMIT 10;

-- Bottom 10 (coolest / lowest risk) for the same year.
SELECT r.rank, w.ward_name, w.corporation, m.lst_mean_c, m.ndvi_mean, m.built_frac, r.composite_risk, r.delta_lst_c
FROM `penumbra-509416.penumbra.ward_risk` AS r
JOIN `penumbra-509416.penumbra.wards_clean` AS w USING (ward_key)
JOIN `penumbra-509416.penumbra.ward_metrics` AS m ON m.ward_key = r.ward_key AND m.year = r.year
WHERE r.year = 2025
ORDER BY r.rank DESC
LIMIT 10;

-- Quick check that the reweighting TVF works and reorders under an extreme weight.
SELECT ward_key, composite_risk, rank
FROM `penumbra-509416.penumbra.ward_risk_reweighted`(2025, 0.0, 1.0, 0.0, 0.0)
ORDER BY rank
LIMIT 5;
