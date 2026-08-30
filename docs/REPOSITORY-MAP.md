# Repository map

| Path | Purpose | Must not contain |
| --- | --- | --- |
| `ml/phase1/training` | Dataset, U-Net training, validation selection | Production API code |
| `ml/phase1/evaluation` | Locked test evaluation and error gallery | Threshold tuning on test |
| `services/detection-engine` | Frozen model inference and Phase 1 artifacts | Optimizer, epochs, training data |
| `services/drift-engine` | OpenDrift/OpenOil runs and Phase 2 artifacts | Browser API responsibilities |
| `services/ais-engine` | AIS ETL/features/score-v1 | Public MMSI projection |
| `apps/api` | NestJS, pg-boss, persistence, public DTOs | Scientific calculations duplicated from engines |
| `apps/web` | MapLibre dashboard | Hard-coded scientific results |
| `packages/contracts` | Canonical schemas and golden fixtures | Independently conflicting payloads |

## Model promotion

`EXPERIMENTAL -> VALIDATED -> APPROVED -> PRODUCTION`

Only an approved package containing weights, preprocessing profile, threshold, model card, evaluation summary and checksums may be loaded by `detection-engine`.
