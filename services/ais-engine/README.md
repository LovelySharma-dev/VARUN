# VARUN Phase 3 AIS Engine

Scientific candidate ranking pipeline.

## Pipeline

Phase 2 search window
→ bounded AIS candidates
→ track reconstruction
→ feature extraction
→ negative evidence
→ explainable score-v1
→ deterministic Top-3

## Score

The score is an investigative ranking score.

It is NOT:

- guilt probability
- legal attribution
- proof of responsibility
- ground-truth probability

## Privacy

Public responses must not contain:

- MMSI
- ground truth
- confirmed culprit labels

## Scientific features

- origin proximity
- time overlap
- corridor overlap
- speed behaviour
- course behaviour
- AIS gap quality
- track coverage
- data quality

## Provenance

Each candidate must retain:

- source
- provider
- synthetic flag

## Run

uvicorn app.main:app --host 0.0.0.0 --port 8003

## Test

pytest -q
