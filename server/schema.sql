-- tool_results: audit trail for every tool call an agent makes, and the
-- backing data for the source drawer (GET /api/sources/{tool_result_id}).
-- Run once: bq query --use_legacy_sql=false < server/schema.sql

CREATE TABLE IF NOT EXISTS `penumbra-509416.penumbra.tool_results` (
  tool_result_id STRING NOT NULL,
  tool_name STRING NOT NULL,
  params_json STRING NOT NULL,
  result_json STRING NOT NULL,
  created_at TIMESTAMP NOT NULL
);
