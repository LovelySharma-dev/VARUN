# Phase 1 detection engine

Private FastAPI production-inference service. Loads one approved model package and performs deterministic preprocessing, tiling, inference, stitching, polygonisation, geometry calculation, artifact export and provenance recording.

No training loop, optimiser, augmentation experiments or threshold selection belongs here.
