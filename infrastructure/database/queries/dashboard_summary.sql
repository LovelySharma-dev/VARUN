-- Parameter: $1 = case_id, $2 = optional phase3 analysis_run_id.
-- This is a lightweight read model. Heavy tracks/rasters remain artifacts.
SELECT
  c.case_id,
  c.case_code,
  c.title,
  c.data_origin,
  jsonb_agg(
    jsonb_build_object(
      'runId', r.analysis_run_id,
      'phase', r.phase,
      'status', r.status,
      'inputContractVersion', r.input_contract_version,
      'outputContractVersion', r.output_contract_version,
      'createdAt', r.created_at
    ) ORDER BY r.created_at
  ) AS runs
FROM cases c
LEFT JOIN analysis_runs r ON r.case_id = c.case_id
WHERE c.case_id = $1::uuid
  AND ($2::uuid IS NULL OR r.analysis_run_id = $2::uuid OR r.phase <> 'PHASE3')
GROUP BY c.case_id;
