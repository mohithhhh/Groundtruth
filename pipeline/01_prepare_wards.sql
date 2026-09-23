-- Phase 1, step 1: validate the source `wards` table and build `wards_clean`.
-- Run with: bq query --use_legacy_sql=false < pipeline/01_prepare_wards.sql
-- (or run the two statements separately: validation first, then the CREATE TABLE)

-- ---------------------------------------------------------------------------
-- Validation: must return 369 / 369 / 5 and zero null/empty geometries before
-- proceeding. If distinct_id2 != total_rows, id2 is not a safe unique key and
-- the pipeline must stop here (per CLAUDE.md ground rules).
-- ---------------------------------------------------------------------------
SELECT
  COUNT(*) AS total_rows,
  COUNT(DISTINCT id2) AS distinct_id2,
  COUNT(DISTINCT Corporation) AS distinct_corporations,
  COUNTIF(geometry IS NULL) AS null_geometry,
  COUNTIF(ST_ISEMPTY(geometry)) AS empty_geometry
FROM `penumbra-509416.penumbra.wards`;

-- ---------------------------------------------------------------------------
-- wards_clean: normalized column names, computed area and centroid.
--
-- Deviation from CLAUDE.md: BigQuery GEOGRAPHY has no ST_ISVALID function.
-- Geography values are validated/snapped to valid geometry at ingestion time
-- (backed by S2), so there is no separate "invalid but stored" state to check
-- for. We check null/empty geometry instead. See docs/DECISIONS.md.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE `penumbra-509416.penumbra.wards_clean` AS
SELECT
  'bengaluru' AS city_id,
  id2 AS ward_key,
  ward_id AS ward_no,
  ward_name,
  ward_name_kn,
  Corporation AS corporation,
  corporation_kn,
  ac,
  ac_no,
  geometry,
  ST_AREA(geometry) / 1e6 AS area_km2,
  ST_CENTROID(geometry) AS centroid
FROM `penumbra-509416.penumbra.wards`;

-- ---------------------------------------------------------------------------
-- Exit check: 369 rows, 5 corporations, no null centroid/area.
-- ---------------------------------------------------------------------------
SELECT
  COUNT(*) AS total_rows,
  COUNT(DISTINCT corporation) AS distinct_corporations,
  COUNTIF(centroid IS NULL) AS null_centroid,
  COUNTIF(area_km2 IS NULL OR area_km2 <= 0) AS bad_area
FROM `penumbra-509416.penumbra.wards_clean`;
