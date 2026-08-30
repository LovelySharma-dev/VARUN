# Chunked database implementation prompts

## Prompt 0 - Review before migration

```text
We are implementing the SIH26143 VARUN database, database chunk 0 only.
Read docs/DATABASE-DESIGN.md, infrastructure/database migrations and
packages/contracts. Check exact Phase 1/2/3 field names, UTC, SRID 4326,
origin_evidence_surface, candidateId privacy, immutable retries and synthetic
ground-truth isolation. Report conflicts and a minimal patch. Do not generate
repositories or UI yet.
```

## Prompt 1 - Apply and test core migration

```text
Implement database chunk 1 only. Use the existing reviewed SQL migrations as
canonical. Add an idempotent PowerShell migration runner and SQL integration
tests for PostGIS, UTC, coordinate order, checksums, immutable retries,
artifact lineage and role permissions. Do not use prisma db push. Provide
exact Windows commands and expected PASS output.
```

## Prompt 2 - NestJS core repositories

```text
Implement database chunk 2 only in apps/api. Generate NestJS modules and
repositories for Case, Scene, AnalysisRun, RunEvent, Artifact, Warning,
DashboardLayer and TimelineFrame. Use Prisma transactions for CRUD and
parameterized pg SQL for geometry. Validate DTOs with canonical Zod schemas.
Do not implement scientific calculations or Phase 3 identity endpoints.
Add integration tests and preserve immutable retry rules.
```

## Prompt 3 - Phase 1 persistence

```text
Implement database chunk 3 only: model_versions, phase1_results,
detection_regions and phase1_metric_sets. Persist model/preprocessing/
threshold versions, scientific artifact references and metrics availability.
Use OIL_LIKELIHOOD wording. Without ground truth return NOT_AVAILABLE rather
than invented Dice/IoU. Add known synthetic geometry fixtures and PostGIS tests.
```

## Prompt 4 - Phase 2 persistence

```text
Implement database chunk 4 only: environmental datasets, Phase 2 run result,
drift scenarios, origin regions, reconstruction metrics, forecast summary and
phase2-to-phase3-v1 handoff. Store origin_evidence_surface artifact references;
do not create origin_probability. Add release-window, buffer, CRS, checksum and
contract tests.
```

## Prompt 5 - AIS and privacy

```text
Implement database chunk 5 only: bounded AIS dataset/ingest, restricted vessel
identity, bulk AIS point/segment ingestion and public candidateId projection.
Use random UUID candidateId, parameterized COPY/SQL and GiST/time indexes.
Add tests proving public DTOs, logs, GeoJSON and URLs contain zero MMSI.
Do not expose scenario_ground_truth to scoring roles.
```

## Prompt 6 - Features, scores and dashboard

```text
Implement database chunk 6 only: candidate decisions, features, evidence
events, score components/rankings and complete-dashboard read repositories.
Score is an investigative index, not probability. Persist raw value, normalized
value, unit, weight, contribution, deduction/cap and reason. Heavy tracks are
lazy-loaded artifacts. Add deterministic ranking, privacy and query-count tests.
```

## Error prompt

```text
Current database chunk: [X]. Exact command: [command]. Complete error/log:
[paste]. Expected: [expected]. Actual: [actual]. Relevant migration/schema/test
files are attached. Find the root cause and return the smallest safe patch plus
a regression test. Do not rewrite previous migrations, weaken privacy, use
prisma db push or rename canonical contract fields.
```
