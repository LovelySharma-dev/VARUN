# Database easy guide (Hinglish)

## Database ko kaise sochna hai

Database scientific files ka godown nahi hai. Database investigation ki indexed diary hai:

- kis case par kaunsa scene use hua;
- kis run ne kya input/config/model use kiya;
- result files kahan hain aur unka checksum kya hai;
- Phase 1 ka output Phase 2 ko aur Phase 2 ka output Phase 3 ko kaise mila;
- dashboard par dikhne wali value kis evidence se aayi;
- result real, synthetic ya mixed data par bana.

## Core flow

1. `cases`: poori investigation.
2. `scenes`: case ke satellite observations.
3. `analysis_runs`: Phase 1/2/3 ki immutable attempts.
4. `run_events`: queued se completed/failed tak history.
5. `artifacts`: external result files ke safe references.
6. `handoffs`: exact versioned phase-to-phase JSON.
7. `dashboard_layers` and `timeline_frames`: frontend read model.

## Phase 1

`model_versions` tells which approved U-Net/checkpoint, preprocessing and threshold were used. `phase1_results` is the scene-level summary. Every separate detected patch is a `detection_region`, with GeoJSON-compatible geometry, centroid, area and likelihood summary. Metrics are stored with availability context; without ground truth, the scene metric is `NOT_AVAILABLE`.

## Phase 2

`environmental_datasets` records currents/wind/waves/coast coverage and versions. `drift_scenarios` stores each candidate age/particle/perturbation run. `origin_regions` stores density contours and alternatives. `reconstruction_metrics` explains why a release candidate is stronger. `phase2_results` carries the canonical search region/release window for Phase 3.

## Phase 3

AIS raw identity is restricted. Clean points and segments link to an internal `identity_id`. When a vessel enters a Phase 3 candidate set, a random public `candidate_id` is created. Features, evidence events and scores link to this public candidate. The public view cannot reveal MMSI.

## Real versus synthetic

Use `REAL` for verified provider data, `SYNTHETIC` for generated controlled tests and `MIXED` when real traffic contains an injected synthetic target. A synthetic known vessel belongs in `scenario_ground_truth`; scoring cannot query it. It is used only after scoring to measure Recall@1/3/5 and MRR.

Never use synthetic fixtures to claim real-world accuracy. Never mark a real unverified vessel as ground truth.

## Why files are outside DB

GeoTIFF, NetCDF, Parquet and model weights can be large. Keeping them in the database makes backup, queries and the laptop demo unnecessarily heavy. `artifacts` stores URI, SHA-256, MIME type, size, bounds, time range and metadata; the original file remains in the artifact directory/object store.

## Which technology does what

- Prisma: cases, runs, warnings, candidate records, scores and transactions.
- `pg` parameterized SQL: `ST_Intersects`, `ST_DWithin`, spatial filtering and bulk AIS operations.
- PostGIS: geometries and spatial indexes.
- pg-boss: actual job queue tables; `job_executions` only shows domain status/correlation.
- NestJS: public privacy-safe API and complete dashboard composition.
- FastAPI services: scientific computation and deterministic artifact production.

## First implementation milestone

Do not create all UI screens first. Apply core migration, load the synthetic smoke case and prove:

1. UTC survives round trip.
2. GeoJSON remains `[longitude, latitude]`.
3. PostGIS intersection/distance works.
4. A retry creates a new run.
5. An artifact links to one immutable run.
6. Scoring role cannot read ground truth.
7. Public candidate view contains no MMSI.

After this PASS gate, implement Phase 1 repositories and continue phase-wise.
