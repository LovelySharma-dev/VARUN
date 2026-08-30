# Database verification checklist

## Apply locally

```powershell
docker compose up -d postgis
psql "$env:DATABASE_URL" -f infrastructure/database/migrations/001_initial_schema.sql
psql "$env:DATABASE_URL" -f infrastructure/database/migrations/002_roles_and_privacy.sql
psql "$env:DATABASE_URL" -f infrastructure/database/seed/001_synthetic_case.sql
```

## Required checks

1. `SELECT PostGIS_Version();` succeeds.
2. Synthetic case/scene return `SYNTHETIC` and the UTC timestamp unchanged.
3. `ST_AsGeoJSON(footprint)` retains longitude/latitude order.
4. A duplicate case code, scene external ID or candidate feature version fails.
5. Invalid 61-character checksum and invalid 8-digit MMSI fail constraints.
6. Retry creates a new `analysis_runs` row linked through `retry_of_run_id`.
7. `varun_scoring` cannot select `scenario_ground_truth`.
8. `public_candidate_rankings` has no MMSI or `identity_id` column.
9. `EXPLAIN ANALYZE` for candidate filtering uses spatial/time indexes on the bounded fixture.
10. Artifact, layer and timeline references resolve before a run becomes completed.

## Synthetic-data gate

- Synthetic fixture is visibly marked in DB, API and dashboard.
- `ground_truth.json`/`scenario_ground_truth` is read only by evaluator code.
- Feature/scoring tests fail if a ground-truth field enters their input DTO.
- Never combine synthetic held-out cases with development weight tuning.
