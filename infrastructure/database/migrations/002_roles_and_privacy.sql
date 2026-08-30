BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'varun_app') THEN
    CREATE ROLE varun_app NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'varun_scoring') THEN
    CREATE ROLE varun_scoring NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'varun_evaluator') THEN
    CREATE ROLE varun_evaluator NOLOGIN;
  END IF;
END $$;

REVOKE ALL ON restricted_vessel_identities FROM PUBLIC;
REVOKE ALL ON scenario_ground_truth FROM PUBLIC;

GRANT SELECT ON public_candidate_rankings TO varun_app;
GRANT SELECT, INSERT, UPDATE ON phase3_candidates, candidate_decisions,
  candidate_features, evidence_events, candidate_scores, score_components
  TO varun_scoring;
GRANT SELECT ON scenario_ground_truth, controlled_scenarios TO varun_evaluator;

REVOKE ALL ON scenario_ground_truth FROM varun_scoring;

COMMIT;
