BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE data_origin AS ENUM ('REAL','SYNTHETIC','MIXED');
CREATE TYPE phase_code AS ENUM ('PHASE1','PHASE2','PHASE3');
CREATE TYPE run_status AS ENUM ('QUEUED','VALIDATING','LOADING_INPUT','PROCESSING','PACKAGING','COMPLETED','COMPLETED_WITH_WARNINGS','FAILED','CANCELLED');
CREATE TYPE artifact_role AS ENUM ('SCIENTIFIC','DASHBOARD','HANDOFF','REPORT','MODEL','DATASET');
CREATE TYPE availability_status AS ENUM ('AVAILABLE','NOT_AVAILABLE','INSUFFICIENT_DATA','NOT_APPLICABLE');
CREATE TYPE evidence_confidence AS ENUM ('HIGH','MEDIUM','LOW','INSUFFICIENT');
CREATE TYPE point_source AS ENUM ('OBSERVED','INTERPOLATED');
CREATE TYPE decision_kind AS ENUM ('INCLUDED','EXCLUDED');
CREATE TYPE evidence_kind AS ENUM ('ORIGIN','TIME','CORRIDOR','PROXIMITY','BEHAVIOUR','DATA_QUALITY','NEGATIVE');

CREATE TABLE cases (
  case_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_code text NOT NULL UNIQUE,
  title text NOT NULL,
  description text,
  data_origin data_origin NOT NULL,
  region geometry(Geometry,4326),
  status text NOT NULL DEFAULT 'OPEN',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE scenes (
  scene_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES cases(case_id),
  external_scene_id text NOT NULL,
  sensor text NOT NULL,
  acquisition_time_utc timestamptz NOT NULL,
  footprint geometry(Geometry,4326) NOT NULL,
  crs text NOT NULL,
  data_origin data_origin NOT NULL,
  source_uri text,
  source_checksum_sha256 text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(case_id, external_scene_id),
  CHECK (source_checksum_sha256 IS NULL OR source_checksum_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE TABLE analysis_runs (
  analysis_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES cases(case_id),
  scene_id uuid REFERENCES scenes(scene_id),
  phase phase_code NOT NULL,
  status run_status NOT NULL DEFAULT 'QUEUED',
  data_origin data_origin NOT NULL,
  retry_of_run_id uuid REFERENCES analysis_runs(analysis_run_id),
  idempotency_key text,
  input_contract_version text NOT NULL,
  output_contract_version text,
  config_hash text NOT NULL,
  code_version text NOT NULL,
  requested_by text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  input_snapshot jsonb NOT NULL,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at),
  CHECK (config_hash ~ '^[a-f0-9]{64}$')
);

CREATE UNIQUE INDEX analysis_runs_idempotency_uq
  ON analysis_runs(case_id, phase, idempotency_key)
  WHERE idempotency_key IS NOT NULL;

CREATE TABLE run_events (
  run_event_id bigserial PRIMARY KEY,
  analysis_run_id uuid NOT NULL REFERENCES analysis_runs(analysis_run_id),
  status run_status NOT NULL,
  stage text NOT NULL,
  progress_percent numeric(5,2),
  safe_message text,
  error_code text,
  retryable boolean,
  correlation_id text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  CHECK (progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100)
);

CREATE TABLE job_executions (
  job_execution_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES analysis_runs(analysis_run_id),
  queue_name text NOT NULL,
  boss_job_id uuid,
  idempotency_key text NOT NULL UNIQUE,
  attempt_no integer NOT NULL DEFAULT 1 CHECK (attempt_no > 0),
  status text NOT NULL,
  correlation_id text NOT NULL,
  available_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  safe_error jsonb
);

CREATE TABLE artifacts (
  artifact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES analysis_runs(analysis_run_id),
  role artifact_role NOT NULL,
  logical_name text NOT NULL,
  artifact_version text NOT NULL,
  uri text NOT NULL,
  media_type text NOT NULL,
  checksum_sha256 text NOT NULL,
  size_bytes bigint CHECK (size_bytes IS NULL OR size_bytes >= 0),
  bounds geometry(Geometry,4326),
  time_start_utc timestamptz,
  time_end_utc timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(analysis_run_id, logical_name, artifact_version),
  CHECK (checksum_sha256 ~ '^[a-f0-9]{64}$'),
  CHECK (time_end_utc IS NULL OR time_start_utc IS NULL OR time_end_utc >= time_start_utc)
);

CREATE TABLE run_warnings (
  warning_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES analysis_runs(analysis_run_id),
  code text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('INFO','WARNING','CRITICAL')),
  message text NOT NULL,
  stage text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE dashboard_layers (
  dashboard_layer_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES analysis_runs(analysis_run_id),
  artifact_id uuid NOT NULL REFERENCES artifacts(artifact_id),
  layer_key text NOT NULL,
  kind text NOT NULL,
  role text NOT NULL,
  visible_by_default boolean NOT NULL DEFAULT false,
  display_order integer NOT NULL DEFAULT 0,
  style jsonb NOT NULL DEFAULT '{}'::jsonb,
  availability availability_status NOT NULL DEFAULT 'AVAILABLE',
  UNIQUE(analysis_run_id, layer_key)
);

CREATE TABLE timeline_frames (
  timeline_frame_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES analysis_runs(analysis_run_id),
  dashboard_layer_id uuid REFERENCES dashboard_layers(dashboard_layer_id),
  frame_time_utc timestamptz NOT NULL,
  relative_seconds integer NOT NULL,
  artifact_id uuid REFERENCES artifacts(artifact_id),
  availability availability_status NOT NULL DEFAULT 'AVAILABLE',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(analysis_run_id, dashboard_layer_id, frame_time_utc)
);

CREATE TABLE handoffs (
  handoff_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_run_id uuid NOT NULL REFERENCES analysis_runs(analysis_run_id),
  target_phase phase_code NOT NULL,
  target_run_id uuid REFERENCES analysis_runs(analysis_run_id),
  contract_version text NOT NULL,
  payload jsonb NOT NULL,
  checksum_sha256 text NOT NULL,
  validation_status text NOT NULL,
  validation_report jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(source_run_id, target_phase, contract_version),
  CHECK (checksum_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE TABLE model_versions (
  model_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_name text NOT NULL,
  semantic_version text NOT NULL,
  stage text NOT NULL CHECK (stage IN ('EXPERIMENTAL','VALIDATED','APPROVED','PRODUCTION','RETIRED')),
  architecture text NOT NULL,
  framework text NOT NULL,
  input_profile text NOT NULL,
  preprocessing_version text NOT NULL,
  threshold_version text NOT NULL,
  threshold_value numeric NOT NULL CHECK (threshold_value BETWEEN 0 AND 1),
  package_artifact_id uuid REFERENCES artifacts(artifact_id),
  evaluation_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  approved_at timestamptz,
  UNIQUE(model_name, semantic_version)
);

CREATE TABLE phase1_results (
  analysis_run_id uuid PRIMARY KEY REFERENCES analysis_runs(analysis_run_id),
  model_version_id uuid NOT NULL REFERENCES model_versions(model_version_id),
  observation_time_utc timestamptz NOT NULL,
  scene_metric_availability availability_status NOT NULL,
  detection_count integer NOT NULL DEFAULT 0 CHECK (detection_count >= 0),
  summary jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE detection_regions (
  detection_region_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES phase1_results(analysis_run_id),
  region_no integer NOT NULL,
  classification text NOT NULL DEFAULT 'OIL_LIKELIHOOD',
  geometry geometry(Geometry,4326) NOT NULL,
  core_geometry geometry(Geometry,4326),
  outer_geometry geometry(Geometry,4326),
  centroid geometry(Point,4326) NOT NULL,
  area_m2 numeric CHECK (area_m2 IS NULL OR area_m2 >= 0),
  perimeter_m numeric CHECK (perimeter_m IS NULL OR perimeter_m >= 0),
  orientation_deg numeric,
  mean_likelihood numeric CHECK (mean_likelihood IS NULL OR mean_likelihood BETWEEN 0 AND 1),
  properties jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(analysis_run_id, region_no)
);

CREATE TABLE phase1_metric_sets (
  phase1_metric_set_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES phase1_results(analysis_run_id),
  context text NOT NULL,
  dataset_version text,
  availability availability_status NOT NULL,
  sample_count integer CHECK (sample_count IS NULL OR sample_count >= 0),
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  reason text,
  UNIQUE(analysis_run_id, context)
);

CREATE TABLE environmental_datasets (
  environmental_dataset_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES cases(case_id),
  dataset_version text NOT NULL,
  provider text NOT NULL,
  product_id text NOT NULL,
  variables jsonb NOT NULL,
  units jsonb NOT NULL,
  coverage geometry(Geometry,4326) NOT NULL,
  time_start_utc timestamptz NOT NULL,
  time_end_utc timestamptz NOT NULL,
  checksum_sha256 text NOT NULL,
  licence_note text,
  data_origin data_origin NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(case_id, dataset_version),
  CHECK (time_end_utc >= time_start_utc),
  CHECK (checksum_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE TABLE phase2_results (
  analysis_run_id uuid PRIMARY KEY REFERENCES analysis_runs(analysis_run_id),
  phase1_run_id uuid NOT NULL REFERENCES phase1_results(analysis_run_id),
  environmental_dataset_id uuid NOT NULL REFERENCES environmental_datasets(environmental_dataset_id),
  detection_time_utc timestamptz NOT NULL,
  release_start_utc timestamptz NOT NULL,
  release_end_utc timestamptz NOT NULL,
  time_buffer_minutes integer NOT NULL CHECK (time_buffer_minutes >= 0),
  search_region geometry(Geometry,4326) NOT NULL,
  spatial_buffer_m numeric NOT NULL CHECK (spatial_buffer_m >= 0),
  hindcast_corridor geometry(Geometry,4326),
  evidence_mode text NOT NULL,
  origin_evidence_artifact_id uuid REFERENCES artifacts(artifact_id),
  summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK (release_end_utc >= release_start_utc)
);

CREATE TABLE drift_scenarios (
  drift_scenario_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES phase2_results(analysis_run_id),
  scenario_code text NOT NULL,
  candidate_age_hours numeric,
  particle_count integer NOT NULL CHECK (particle_count > 0),
  random_seed bigint NOT NULL,
  direction text NOT NULL CHECK (direction IN ('BACKWARD','FORWARD_RECONSTRUCTION','FORWARD_FORECAST','SMOKE')),
  forcing_perturbation jsonb NOT NULL DEFAULT '{}'::jsonb,
  boundary_variant text,
  oil_scenario jsonb,
  config_hash text NOT NULL,
  status text NOT NULL,
  UNIQUE(analysis_run_id, scenario_code),
  CHECK (config_hash ~ '^[a-f0-9]{64}$')
);

CREATE TABLE origin_regions (
  origin_region_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES phase2_results(analysis_run_id),
  region_code text NOT NULL,
  contour_level integer CHECK (contour_level IS NULL OR contour_level IN (50,75,90)),
  mode_rank integer,
  geometry geometry(Geometry,4326) NOT NULL,
  evidence_value numeric,
  evidence_semantics text NOT NULL,
  release_start_utc timestamptz,
  release_end_utc timestamptz,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(analysis_run_id, region_code)
);

CREATE TABLE reconstruction_metrics (
  reconstruction_metric_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES phase2_results(analysis_run_id),
  drift_scenario_id uuid NOT NULL REFERENCES drift_scenarios(drift_scenario_id),
  centroid_error_m numeric CHECK (centroid_error_m IS NULL OR centroid_error_m >= 0),
  iou numeric CHECK (iou IS NULL OR iou BETWEEN 0 AND 1),
  containment numeric CHECK (containment IS NULL OR containment BETWEEN 0 AND 1),
  orientation_error_deg numeric,
  area_error_ratio numeric,
  forward_consistency_score numeric,
  metric_version text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(analysis_run_id, drift_scenario_id)
);

CREATE TABLE forecast_summaries (
  analysis_run_id uuid PRIMARY KEY REFERENCES phase2_results(analysis_run_id),
  forecast_start_utc timestamptz NOT NULL,
  forecast_end_utc timestamptz NOT NULL,
  oil_scenario jsonb NOT NULL,
  coastal_contact_status text NOT NULL,
  earliest_contact_utc timestamptz,
  coastal_geometry geometry(Geometry,4326),
  availability availability_status NOT NULL,
  warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
  CHECK (forecast_end_utc >= forecast_start_utc)
);

CREATE TABLE ais_datasets (
  ais_dataset_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES cases(case_id),
  dataset_version text NOT NULL,
  provider text NOT NULL,
  source_id text NOT NULL,
  licence_note text NOT NULL,
  data_origin data_origin NOT NULL,
  coverage geometry(Geometry,4326) NOT NULL,
  time_start_utc timestamptz NOT NULL,
  time_end_utc timestamptz NOT NULL,
  checksum_sha256 text NOT NULL,
  public_identity_policy text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(case_id, dataset_version),
  CHECK (time_end_utc >= time_start_utc),
  CHECK (checksum_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE TABLE ais_ingests (
  ais_ingest_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ais_dataset_id uuid NOT NULL REFERENCES ais_datasets(ais_dataset_id),
  ingest_version text NOT NULL,
  raw_row_count bigint NOT NULL CHECK (raw_row_count >= 0),
  clean_row_count bigint NOT NULL CHECK (clean_row_count >= 0),
  duplicate_count bigint NOT NULL DEFAULT 0 CHECK (duplicate_count >= 0),
  rejected_count bigint NOT NULL DEFAULT 0 CHECK (rejected_count >= 0),
  quality_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  config_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(ais_dataset_id, ingest_version),
  CHECK (config_hash ~ '^[a-f0-9]{64}$')
);

CREATE TABLE restricted_vessel_identities (
  identity_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ais_dataset_id uuid NOT NULL REFERENCES ais_datasets(ais_dataset_id),
  mmsi text,
  provider_vessel_id text,
  approved_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  restricted_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(ais_dataset_id, mmsi),
  CHECK (mmsi IS NULL OR mmsi ~ '^[0-9]{9}$')
);

CREATE TABLE ais_points (
  ais_point_id bigserial PRIMARY KEY,
  ais_ingest_id uuid NOT NULL REFERENCES ais_ingests(ais_ingest_id),
  identity_id uuid NOT NULL REFERENCES restricted_vessel_identities(identity_id),
  observed_at timestamptz NOT NULL,
  position geometry(Point,4326) NOT NULL,
  sog_knots numeric,
  cog_deg numeric,
  heading_deg numeric,
  nav_status text,
  quality_flags jsonb NOT NULL DEFAULT '[]'::jsonb,
  raw_ref jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK (cog_deg IS NULL OR cog_deg BETWEEN 0 AND 360),
  CHECK (heading_deg IS NULL OR heading_deg BETWEEN 0 AND 360)
);

CREATE TABLE ais_track_segments (
  track_segment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ais_ingest_id uuid NOT NULL REFERENCES ais_ingests(ais_ingest_id),
  identity_id uuid NOT NULL REFERENCES restricted_vessel_identities(identity_id),
  started_at timestamptz NOT NULL,
  ended_at timestamptz NOT NULL,
  source_kind point_source NOT NULL,
  track geometry(LineString,4326) NOT NULL,
  observed_point_count integer NOT NULL DEFAULT 0,
  interpolated_point_count integer NOT NULL DEFAULT 0,
  coverage_ratio numeric CHECK (coverage_ratio IS NULL OR coverage_ratio BETWEEN 0 AND 1),
  largest_gap_seconds integer CHECK (largest_gap_seconds IS NULL OR largest_gap_seconds >= 0),
  uncertainty_flags jsonb NOT NULL DEFAULT '[]'::jsonb,
  CHECK (ended_at >= started_at)
);

CREATE TABLE phase3_candidates (
  candidate_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES analysis_runs(analysis_run_id),
  identity_id uuid NOT NULL REFERENCES restricted_vessel_identities(identity_id),
  candidate_set_version text NOT NULL,
  public_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(analysis_run_id, identity_id),
  UNIQUE(analysis_run_id, candidate_id)
);

CREATE TABLE candidate_decisions (
  candidate_decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_run_id uuid NOT NULL REFERENCES analysis_runs(analysis_run_id),
  identity_id uuid NOT NULL REFERENCES restricted_vessel_identities(identity_id),
  candidate_id uuid REFERENCES phase3_candidates(candidate_id),
  decision decision_kind NOT NULL,
  reason_code text NOT NULL,
  contact_type text,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  config_hash text NOT NULL,
  decided_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(analysis_run_id, identity_id),
  CHECK (config_hash ~ '^[a-f0-9]{64}$')
);

CREATE TABLE candidate_features (
  candidate_feature_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES phase3_candidates(candidate_id),
  feature_name text NOT NULL,
  feature_version text NOT NULL,
  raw_value numeric,
  normalized_value numeric,
  unit text,
  availability availability_status NOT NULL,
  source_kind point_source,
  confidence_cap numeric CHECK (confidence_cap IS NULL OR confidence_cap BETWEEN 0 AND 1),
  reason text,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(candidate_id, feature_name, feature_version)
);

CREATE TABLE evidence_events (
  evidence_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES phase3_candidates(candidate_id),
  kind evidence_kind NOT NULL,
  event_code text NOT NULL,
  event_time_utc timestamptz,
  time_end_utc timestamptz,
  geometry geometry(Geometry,4326),
  raw_value numeric,
  unit text,
  source_kind point_source,
  explanation text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE candidate_scores (
  candidate_score_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES phase3_candidates(candidate_id),
  score_version text NOT NULL,
  config_hash text NOT NULL,
  investigative_score numeric NOT NULL CHECK (investigative_score BETWEEN 0 AND 100),
  rank integer NOT NULL CHECK (rank > 0),
  confidence evidence_confidence NOT NULL,
  positive_total numeric NOT NULL,
  negative_total numeric NOT NULL DEFAULT 0,
  confidence_cap numeric,
  explanation text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(candidate_id, score_version),
  CHECK (config_hash ~ '^[a-f0-9]{64}$'),
  CHECK (confidence_cap IS NULL OR confidence_cap BETWEEN 0 AND 1)
);

CREATE TABLE score_components (
  score_component_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_score_id uuid NOT NULL REFERENCES candidate_scores(candidate_score_id),
  component_name text NOT NULL,
  raw_value numeric,
  normalized_value numeric,
  weight numeric NOT NULL,
  contribution numeric NOT NULL,
  is_deduction boolean NOT NULL DEFAULT false,
  cap_applied numeric,
  reason text NOT NULL,
  UNIQUE(candidate_score_id, component_name)
);

CREATE TABLE controlled_scenarios (
  controlled_scenario_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scenario_code text NOT NULL UNIQUE,
  case_id uuid NOT NULL REFERENCES cases(case_id),
  data_origin data_origin NOT NULL CHECK (data_origin IN ('SYNTHETIC','MIXED')),
  split text NOT NULL CHECK (split IN ('DEVELOPMENT','HELD_OUT_TEST')),
  scenario_version text NOT NULL,
  description text NOT NULL,
  config_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (config_hash ~ '^[a-f0-9]{64}$')
);

CREATE TABLE scenario_ground_truth (
  controlled_scenario_id uuid PRIMARY KEY REFERENCES controlled_scenarios(controlled_scenario_id),
  target_identity_id uuid NOT NULL REFERENCES restricted_vessel_identities(identity_id),
  release_time_utc timestamptz NOT NULL,
  release_location geometry(Point,4326) NOT NULL,
  truth_source text NOT NULL,
  verified_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX cases_region_gix ON cases USING gist(region);
CREATE INDEX scenes_footprint_gix ON scenes USING gist(footprint);
CREATE INDEX scenes_case_time_idx ON scenes(case_id, acquisition_time_utc);
CREATE INDEX analysis_runs_case_phase_status_idx ON analysis_runs(case_id, phase, status);
CREATE INDEX analysis_runs_scene_idx ON analysis_runs(scene_id);
CREATE INDEX run_events_run_time_idx ON run_events(analysis_run_id, occurred_at);
CREATE INDEX artifacts_bounds_gix ON artifacts USING gist(bounds);
CREATE INDEX artifacts_run_role_idx ON artifacts(analysis_run_id, role);
CREATE INDEX detection_regions_geom_gix ON detection_regions USING gist(geometry);
CREATE INDEX environmental_coverage_gix ON environmental_datasets USING gist(coverage);
CREATE INDEX phase2_search_region_gix ON phase2_results USING gist(search_region);
CREATE INDEX origin_regions_geom_gix ON origin_regions USING gist(geometry);
CREATE INDEX ais_datasets_coverage_gix ON ais_datasets USING gist(coverage);
CREATE INDEX ais_points_position_gix ON ais_points USING gist(position);
CREATE INDEX ais_points_identity_time_idx ON ais_points(identity_id, observed_at);
CREATE INDEX ais_segments_track_gix ON ais_track_segments USING gist(track);
CREATE INDEX ais_segments_identity_time_idx ON ais_track_segments(identity_id, started_at, ended_at);
CREATE INDEX candidate_decisions_run_decision_idx ON candidate_decisions(analysis_run_id, decision);
CREATE INDEX evidence_events_geom_gix ON evidence_events USING gist(geometry);
CREATE INDEX candidate_scores_rank_idx ON candidate_scores(score_version, rank);

CREATE VIEW public_candidate_rankings AS
SELECT
  pc.analysis_run_id,
  pc.candidate_id,
  pc.candidate_set_version,
  pc.public_metadata,
  cs.score_version,
  cs.investigative_score,
  cs.rank,
  cs.confidence,
  cs.explanation
FROM phase3_candidates pc
JOIN candidate_scores cs ON cs.candidate_id = pc.candidate_id;

COMMENT ON VIEW public_candidate_rankings IS
  'Privacy-safe public projection. Never join restricted_vessel_identities in public API queries.';

COMMIT;
