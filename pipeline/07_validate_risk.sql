-- Phase 1, step 7: weight-sensitivity check for the 2025 ward_risk ranking.
-- Run with: bq query --use_legacy_sql=false < pipeline/07_validate_risk.sql
--
-- For each of the 4 weight components (heat 0.4, green 0.2, built 0.15,
-- exposure 0.25), perturb it by +-0.1 and rescale the other three
-- proportionally so weights still sum to 1, recompute ranks via
-- ward_risk_reweighted, and report the Spearman correlation (= Pearson
-- correlation of the rank columns) against the default-weight ranking.

WITH baseline AS (
  SELECT ward_key, rank AS baseline_rank
  FROM `penumbra-509416.penumbra.ward_risk`
  WHERE year = 2025
)
SELECT 'heat +0.1' AS label, ROUND(CORR(b.baseline_rank, rr.rank), 4) AS spearman_rho
FROM `penumbra-509416.penumbra.ward_risk_reweighted`(2025, 0.5, 0.16666667, 0.125, 0.20833333) AS rr
JOIN baseline AS b USING (ward_key)

UNION ALL
SELECT 'heat -0.1', ROUND(CORR(b.baseline_rank, rr.rank), 4)
FROM `penumbra-509416.penumbra.ward_risk_reweighted`(2025, 0.3, 0.23333333, 0.175, 0.29166667) AS rr
JOIN baseline AS b USING (ward_key)

UNION ALL
SELECT 'green +0.1', ROUND(CORR(b.baseline_rank, rr.rank), 4)
FROM `penumbra-509416.penumbra.ward_risk_reweighted`(2025, 0.35, 0.3, 0.13125, 0.21875) AS rr
JOIN baseline AS b USING (ward_key)

UNION ALL
SELECT 'green -0.1', ROUND(CORR(b.baseline_rank, rr.rank), 4)
FROM `penumbra-509416.penumbra.ward_risk_reweighted`(2025, 0.45, 0.1, 0.16875, 0.28125) AS rr
JOIN baseline AS b USING (ward_key)

UNION ALL
SELECT 'built +0.1', ROUND(CORR(b.baseline_rank, rr.rank), 4)
FROM `penumbra-509416.penumbra.ward_risk_reweighted`(2025, 0.35294118, 0.17647059, 0.25, 0.22058824) AS rr
JOIN baseline AS b USING (ward_key)

UNION ALL
SELECT 'built -0.1', ROUND(CORR(b.baseline_rank, rr.rank), 4)
FROM `penumbra-509416.penumbra.ward_risk_reweighted`(2025, 0.44705882, 0.22352941, 0.05, 0.27941176) AS rr
JOIN baseline AS b USING (ward_key)

UNION ALL
SELECT 'exposure +0.1', ROUND(CORR(b.baseline_rank, rr.rank), 4)
FROM `penumbra-509416.penumbra.ward_risk_reweighted`(2025, 0.34666667, 0.17333333, 0.13, 0.35) AS rr
JOIN baseline AS b USING (ward_key)

UNION ALL
SELECT 'exposure -0.1', ROUND(CORR(b.baseline_rank, rr.rank), 4)
FROM `penumbra-509416.penumbra.ward_risk_reweighted`(2025, 0.45333333, 0.22666667, 0.17, 0.15) AS rr
JOIN baseline AS b USING (ward_key)

ORDER BY label;
