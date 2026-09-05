# VARUNA Phase 3 AIS Backend Integration v1

This document is the deterministic integration handoff for the VARUNA Phase 3
AIS candidate-attribution service. Scores are investigative-priority scores,
not guilt, liability, or responsibility probabilities.

## 1. Repository implementation

| Capability | Repository location |
|---|---|
| FastAPI endpoints | `services/ais-engine/app/main.py` |
| Public camelCase DTOs | `services/ais-engine/app/public_contracts.py` |
| AIS CSV ETL | `services/ais-engine/app/ais_loader.py` |
| Phase 2 bundle validation | `services/ais-engine/app/phase2_loader.py` |
| Candidate time/space filtering | `services/ais-engine/app/candidate_filter.py` |
| Track preprocessing and gap segmentation | `services/ais-engine/app/preprocessing_v21.py` |
| LSTM reconstruction-error inference | `services/ais-engine/app/inference_v21.py` |
| Spatial and temporal evidence | `services/ais-engine/app/candidate_features.py` |
| Behaviour and dark-gap rules | `services/ais-engine/app/behaviour_rules.py` |
| Frozen score-v1 ranking | `services/ais-engine/app/candidate_ranker.py` |
| End-to-end orchestration | `services/ais-engine/app/attribution_pipeline.py` |
| Public artifact generation | `services/ais-engine/app/artifact_writer.py` |
| Model package | `models/phase3/ais-lstm-ae/v2_1/` |
| Reproducibility runner | `services/ais-engine/scripts/run_phase3_reproducibility.py` |
| Contract tests | `services/ais-engine/tests/test_public_phase3_contracts.py` |

## 2. Phase 2 input contract

Contract version: `phase2-to-phase3-v1`.

The source folder must contain these 11 files:

1. `summary.json`
2. `search_window.json`
3. `backward_tracks.geojson`
4. `origin_50.geojson`
5. `origin_75.geojson`
6. `origin_90.geojson`
7. `release_time_scores.csv`
8. `forward_reconstruction.geojson`
9. `reconstruction_metrics.json`
10. `run_config.json`
11. `validation_report.json`

Canonical schema:
`packages/contracts/schemas/phase2-to-phase3-v1.schema.json`.

Canonical consolidated fixture:
`packages/contracts/fixtures/phase2-to-phase3-v1.valid.json`.

Actual folder fixture:
`data/fixtures/phase2-attribution-demo/`.

Required canonical fields include:

- `case_id` and `phase2_run_id`;
- UTC detection and release-window timestamps;
- CRS `EPSG:4326`;
- origin-density contours at 50%, 75%, and 90%;
- polygon search region and spatial buffer;
- hindcast-corridor geometry, direction, and optional time bands;
- provenance.

GeoJSON coordinates are always `[longitude, latitude]`. New code uses
`origin_evidence_surface`; it never labels this evidence as an
`origin_probability`.

## 3. AIS inputs and ETL

### Model-development dataset

- Provider/source: NOAA/MarineCadastre historical AIS.
- Frozen source period: 2025-01-01 through 2025-01-03 UTC.
- Raw file: `us_gulf_3day_raw.parquet`, 4,433,343 rows.
- Fixed-cadence file: `us_gulf_3day_5min.parquet`, 1,548,372 rows.
- Coordinates: WGS84/EPSG:4326, longitude then latitude when serialized as
  GeoJSON.
- Split: grouped by vessel identity, with 1,915 train, 410 validation, and
  411 test vessels; split leakage assertions passed.
- Model training used presumed-normal operational AIS only. Synthetic
  anomalies were used only for a post-training stress test.

### Repository integration fixture

- File: `data/fixtures/ais-phase2-aligned/ais_input.csv`.
- Status: controlled synthetic integration/demo data, not real attribution
  evidence.
- Time range: 2026-08-19T04:30:00Z to 2026-08-19T18:30:00Z.
- Input: 676 observations across 4 vessels.
- Valid time-gated observations: 676.
- Time-and-space matches: 507 observations across 3 candidate vessels.
- Cadence/maximum consecutive fixture gap: 5 minutes.
- Model windows scored: 240.
- Dark gaps detected: 0.

ETL normalizes accepted aliases to `mmsi`, `timestamp`, `latitude`,
`longitude`, `speed`, and `course`; timestamps become UTC; numeric fields are
coerced; invalid identity, time, coordinate, speed, and course rows are
removed; duplicates are removed; and rows are stably sorted by vessel and
timestamp. The ETL audit records original, valid, invalid, duplicate, vessel,
timezone, and coverage information.

MMSI remains restricted internal identity and is replaced by a deterministic
public `candidateId` before public evidence is written.

## 4. Candidate filtering and track reconstruction

Candidate filtering applies the Phase 2 release interval plus its configured
time buffer, followed by the Phase 2 polygon search region plus spatial
buffer. A vessel becomes a candidate only when at least one observation
passes both gates.

Selected observations are ordered per vessel by UTC timestamp. Phase 3 then
computes the frozen eight features, identifies gaps greater than 120 minutes,
and splits each vessel into track segments so an LSTM window never crosses a
dark gap. A segment needs at least 10 observations to produce a model window.

The public reconstructed-track artifact is
`candidate_tracks.geojson`. It contains public `candidateId` values and no
MMSI, IMO, or ship name.

## 5. Frozen LSTM model

- Version: `ais-lstm-ae-v2.1`.
- Type: LSTM autoencoder.
- Input/output: 10 timesteps by 8 scaled features.
- Features: speed, speed change, time difference, step distance, circular
  turn angle, acceleration, net displacement, and path efficiency.
- Scaler: frozen `StandardScaler`, fitted on training-vessel presumed-normal
  rows only.
- Anomaly score: mean squared reconstruction error across all 10 timesteps
  and 8 features.
- Threshold: `0.06935688848908478`, selected as the 95th percentile of the
  frozen presumed-normal validation-window scores.
- Selected-model SHA256:
  `1996072bab24d9325131ca54eb8f13e1f82641f938de5fbdc60eff2aab46d075`.

Synthetic stress-test results: ROC-AUC 0.9407, balanced accuracy 0.8193,
abrupt-manoeuvring recall 0.9692, loitering-transition recall 0.9233, and
sudden-speed-drop recall 0.2050. These are synthetic stress-test metrics, not
real-world responsibility accuracy.

## 6. Feature definitions and score-v1 normalization

Let `clip(x)` mean `min(max(x, 0), 1)`.

| Evidence | Exact score-v1 definition |
|---|---|
| Origin proximity | `exp(-minimumOriginCenterDistanceM / 5000)` |
| Origin dwell | `clip(origin50PointCount / 24)` |
| Release-time alignment | `exp(-closestOriginMidpointOffsetMin / 360)` |
| Corridor alignment | `exp(-minimumCorridorDistanceM / 5000)` |
| Behaviour | Mean of the loitering, abrupt-turn, and sudden-speed-drop Boolean rules |
| LSTM continuous | `clip(maximumReconstructionMse / frozenThreshold)` |
| AIS dark gap | `1` when the candidate has a gap-rule alert, otherwise `0` |

Additional evidence retained outside the weighted formula includes contour
entry flags, `release_window_point_ratio`, raw distances, observation counts,
window counts, and reconstruction errors.

The current behaviour-rule demo thresholds are low speed below 2 knots,
abrupt turn at or above 30 degrees, sudden speed drop at or above 5 knots,
and a dark gap above 120 minutes. These heuristic rule thresholds are not
real-world calibrated.

### Data quality and negative evidence

Data quality is a gate, not an extra score-v1 weight. Invalid and duplicate
records are audited and removed. Candidates with fewer than 10 eligible
consecutive pings cannot be scored and return HTTP 422 rather than receiving
a fabricated score.

Negative evidence is represented by small or zero positive-evidence
components: large origin/corridor distance, low origin dwell, poor temporal
alignment, no behavioural rule, reconstruction error below threshold, no
dark gap, or no contour entry. There is no separately weighted
`negativeEvidence` term in score-v1 and no unvalidated probability claim.

## 7. Frozen score-v1 weights

```text
priority =
    0.25 * origin_proximity_score
  + 0.15 * origin_dwell_score
  + 0.15 * release_time_alignment_score
  + 0.15 * corridor_alignment_score
  + 0.20 * behaviour_rule_score
  + 0.05 * lstm_continuous_score
  + 0.05 * dark_gap_score
```

The weights sum to 1.0. Calibration status is
`CONTROLLED_DEMO_HEURISTIC_NOT_REAL_WORLD_CALIBRATED`.

## 8. Known-target synthetic validation

The controlled demo returns three candidates and 240 scored windows:

| Rank | Candidate ID | Priority score |
|---:|---|---:|
| 1 | `candidate-68f8b1f0ac34` | 0.8721806411 |
| 2 | `candidate-7669d2a91e2d` | 0.6307190116 |
| 3 | `candidate-8fcff6b97422` | 0.1484769382 |

The known target ranks first. `ground_truth.json` is not supplied to or read
by candidate filtering, feature extraction, model inference, or ranking. It
is evaluation-only evidence.

## 9. Output artifacts and actual SHA256

Reference directory: `data/fixtures/phase3-reproducibility-output/`.

| Artifact | SHA256 |
|---|---|
| `ranked_candidates.json` | `374c0b81eae4091b41b34ecd660f5f608f64f49dd05db90d2b84ff9d4adfcb1a` |
| `candidate_features.csv` | `ab9756a8208eafcd3aa2c28976d16c72d57a03a9569a9146e4c9a0ead32021b6` |
| `candidate_tracks.geojson` | `e30e7360d16498c4907affe4086975e537ec96be146c091b6831582cd2ce4b17` |
| `dark_gap_events.json` | `c0fa38add2c15cc375b23f38b829cd77bb6886ba95f7734a82a2d4166eb136a1` |
| `phase3_summary.json` | `0eecfdcad9149174ad16bbee109dd5d01f76ad830b7b9ba61b315a6a32d6643f` |

`sha256_manifest.json` contains the same independently verified hashes.
The summary contains the hashes of the other four artifacts; it cannot
contain its own final hash without a recursive self-hash problem.

## 10. Public API contracts and fixtures

| Purpose | File |
|---|---|
| Request schema | `packages/contracts/schemas/phase3-run-request-v1.schema.json` |
| Success schema | `packages/contracts/schemas/phase3-run-response-v1.schema.json` |
| Error schema | `packages/contracts/schemas/phase3-error-v1.schema.json` |
| Valid request | `packages/contracts/fixtures/phase3-run-v1.request.valid.json` |
| Valid response | `packages/contracts/fixtures/phase3-run-v1.response.valid.json` |
| No-candidate request/response | `packages/contracts/fixtures/phase3-run-v1.request.no-candidate.json` and `phase3-run-v1.response.no-candidate.json` |
| Low-quality request/response | `packages/contracts/fixtures/phase3-run-v1.request.low-ais-quality.json` and `phase3-run-v1.response.low-ais-quality.json` |

The public endpoint is `POST /v1/phase3/run`. The legacy internal endpoint
`POST /run-phase3` remains available and unchanged.

Public JSON uses camelCase. Python internals and CSV columns may use
snake_case. A database may keep `candidate_id`; the NestJS DTO maps it to
public `candidateId`.

Example request:

```json
{
  "phase2Folder": "data/fixtures/phase2-attribution-demo",
  "aisCsvPath": "data/fixtures/ais-phase2-aligned/ais_input.csv",
  "outputDirectory": "artifacts/cases/CASE_DEMO_001/phase3/DRIFT_RUN_001",
  "windowStride": 2,
  "batchSize": 256,
  "topCandidates": 3
}
```

The exact expected response is stored in
`packages/contracts/fixtures/phase3-run-v1.response.valid.json`.

## 11. Error and warning rules

| Condition | Result |
|---|---|
| Required Phase 2 file missing or malformed | HTTP 422 with `detail` |
| Invalid UTC/CRS/time ordering | HTTP 422 with `detail` |
| No vessel passes time and space gates | HTTP 422: `No AIS candidates matched the Phase 2 time/space gate` |
| Candidate has no eligible 10-ping sequence | HTTP 422: `Candidate tracks contain no eligible 10-ping model windows` |
| Output directory already exists | HTTP 422; overwrite is refused |
| Controlled/synthetic Phase 2 warning | Propagated in the public `warnings` array |
| Heuristic ranking | Explicit `calibrationStatus`; no responsibility-probability claim |

## 12. Privacy guarantees

Public schemas and fixtures allow `candidateId` and forbid extra fields.
Public output contains no MMSI, IMO, or ship name. The identity map remains
internal. Ground truth is isolated from filtering and scoring. Automated
tests inject an MMSI into the public response and verify that validation
rejects it.

## 13. Clean Windows execution

From repository root, with Python 3.11 to 3.13:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".\services\ais-engine[dev]"
python -m uvicorn app.main:app --app-dir ".\services\ais-engine" --host 127.0.0.1 --port 8103
```

Health endpoint: `GET http://127.0.0.1:8103/health`.
Swagger: `http://127.0.0.1:8103/docs`.

Starting Uvicorn from repository root, as shown above, makes the fixture's
repository-relative paths directly usable. If Uvicorn is started inside
`services/ais-engine`, use `../../data/...` and `../../artifacts/...` paths.
Container deployments may independently map these to `/app/data/...` and
`/app/artifacts/...` without changing the JSON schema.

## 14. Tests and deterministic replay

```powershell
cd services\ais-engine
python -m pytest -q
python -m scripts.run_phase3_reproducibility --output-root "artifacts/reproducibility/backend_handoff" --batch-size 256
```

Current full suite result: 13 passed. The reproducibility runner performs two
isolated executions and verifies the same candidate set, same order,
byte-identical artifacts, actual hashes, no ground-truth input, and no public
MMSI exposure.

## 15. NestJS integration behaviour

NestJS sends the valid camelCase request fixture to
`POST http://ais-engine:8103/v1/phase3/run`. On HTTP 200 it validates the body
against `phase3-run-response-v1.schema.json`, persists the case/run metadata
and artifact references, and exposes only `candidateId`. On HTTP 422 it
validates `phase3-error-v1.schema.json` and stores/displays the `detail`
message without manufacturing candidate scores.

The current three-candidate controlled result is directly reproducible from
the repository using the committed Phase 2 fixture, AIS fixture, frozen model,
reproducibility script, schemas, and tests described above.
