# 📦 VARUN-ASTRA Python Requirements & Dependencies

This folder contains modular, isolated dependency specifications for each scientific and machine-learning service in the VARUN platform.

---

## 📁 Requirements Structure

| File | Target Component | Key Libraries |
|---|---|---|
| [`requirements-common.txt`](./requirements-common.txt) | Shared FastAPI microservice base | `fastapi`, `uvicorn`, `pydantic`, `httpx`, `numpy`, `python-dotenv` |
| [`requirements-phase1.txt`](./requirements-phase1.txt) | Phase 1 SAR Detection (`services/detection-engine`, `ml/phase1`) | `torch`, `torchvision`, `rasterio`, `pillow`, `matplotlib`, `shapely` |
| [`requirements-phase2.txt`](./requirements-phase2.txt) | Phase 2 Hydrodynamic Drift Engine (`services/drift-engine`) | `scipy`, `shapely`, `geojson` |
| [`requirements-phase3.txt`](./requirements-phase3.txt) | Phase 3 AIS Vessel Attribution (`services/ais-engine`) | `tensorflow`, `keras`, `scikit-learn`, `pandas`, `pyproj`, `joblib` |
| [`requirements-dev.txt`](./requirements-dev.txt) | Monorepo Test & QA Tooling | `pytest`, `pytest-cov`, `black`, `flake8`, `mypy`, `uv` |
| [`requirements-all.txt`](./requirements-all.txt) | Full Monorepo Python Environment | All phases combined |

---

## 🚀 Installation Guide

### Option 1: Fast Install via `uv` (Recommended)

```bash
# Create virtual environment with Python 3.11
uv venv --python 3.11 .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install all monorepo requirements
uv pip install -r requirements/requirements-all.txt
```

### Option 2: Standard `pip`

```bash
# Full environment install
pip install -r requirements/requirements-all.txt

# Or install for a specific service only:
pip install -r requirements/requirements-phase1.txt  # Phase 1 only
pip install -r requirements/requirements-phase2.txt  # Phase 2 only
pip install -r requirements/requirements-phase3.txt  # Phase 3 only
```

---

## 🧪 Service Run Commands

```bash
# Phase 1 Detection Engine (FastAPI :8101)
uvicorn app.main:app --app-dir services/detection-engine --host 0.0.0.0 --port 8101

# Phase 2 Drift Engine (FastAPI :8102)
uvicorn app.main:app --app-dir services/drift-engine --host 0.0.0.0 --port 8102

# Phase 3 AIS Attribution Engine (FastAPI :8103)
uvicorn app.main:app --app-dir services/ais-engine --host 0.0.0.0 --port 8103
```
