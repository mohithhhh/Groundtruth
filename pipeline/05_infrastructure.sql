-- Phase 1, step 5: hospitals and schools from Overture Maps, assigned to wards.
-- Run with: bq query --use_legacy_sql=false < pipeline/05_infrastructure.sql
--
-- Verified 2026-09-24 (see docs/DECISIONS.md):
--   - Table: `bigquery-public-data.overture_maps.place` (US region, 73.6M
--     rows globally, clustered on `geometry`). `bbox.{xmin,xmax,ymin,ymax}`
--     are cheap FLOAT columns -- filtering on them first keeps the scan to
--     tens of MB instead of the full table.
--   - License: every source covering Bengaluru's hospital/school points is
--     CDLA-Permissive-2.0 (Overture, Meta, Microsoft) or Apache-2.0
--     (Foursquare) -- both permissive, safe to use.
--   - Category taxonomy (`categories.primary`) checked live against
--     Bengaluru: kept a deliberately narrow allow-list of core civic
--     hospitals and K-12 schools, excluding medical-supply stores, driving
--     schools, dance/music schools, preschools, etc. that share adjacent
--     category names but aren't what a planner means by "hospital" or
--     "school".

CREATE OR REPLACE TABLE `penumbra-509416.penumbra.infra_points` AS
WITH overture_bengaluru AS (
  SELECT
    id,
    names.primary AS name,
    categories.primary AS category,
    confidence,
    geometry,
    CASE
      WHEN categories.primary = 'hospital' THEN 'hospital'
      WHEN categories.primary IN (
        'school', 'elementary_school', 'middle_school', 'high_school',
        'public_school', 'private_school'
      ) THEN 'school'
    END AS type
  FROM `bigquery-public-data.overture_maps.place`
  WHERE bbox.xmin <= 77.79329079680647 AND bbox.xmax >= 77.45066665638006
    AND bbox.ymin <= 13.151590889081893 AND bbox.ymax >= 12.82452311827992
    AND categories.primary IN (
      'hospital',
      'school', 'elementary_school', 'middle_school', 'high_school',
      'public_school', 'private_school'
    )
)
SELECT
  'bengaluru' AS city_id,
  w.ward_key,
  o.id AS place_id,
  o.name,
  o.type,
  o.category,
  o.confidence
FROM overture_bengaluru AS o
JOIN `penumbra-509416.penumbra.wards_clean` AS w
  ON ST_WITHIN(o.geometry, w.geometry);

-- ---------------------------------------------------------------------------
-- Sanity checks
-- ---------------------------------------------------------------------------

-- Overall counts by type.
SELECT type, COUNT(*) AS n, COUNT(DISTINCT ward_key) AS wards_with_at_least_one
FROM `penumbra-509416.penumbra.infra_points`
GROUP BY type;

-- Wards with zero hospitals and zero schools (plausible for small/green wards,
-- but worth a look, not an error).
SELECT w.ward_key, w.ward_name, w.corporation
FROM `penumbra-509416.penumbra.wards_clean` AS w
LEFT JOIN `penumbra-509416.penumbra.infra_points` AS i USING (ward_key)
WHERE i.ward_key IS NULL
ORDER BY w.ward_key;
