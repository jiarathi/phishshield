# PhishShield v2 (Scam & Phishing Message Analyzer)

A **privacy-conscious**, **measurable**, and **extensible** scam/phishing detection system for consumer texts/messages.

This repo is a clean "start-from-scratch" v2 scaffold that improves on a basic TF‑IDF + regression prototype by adding:
- A **hybrid detection pipeline** (text model + URL intelligence + policy guardrails)
- **Model artifacts** (versioned, reproducible, not trained at API startup)
- **Contracted API schema** (Pydantic models; frontend types match)
- **Evaluation harness** (precision/recall + thresholding focus)
- Safe-by-default design choices (timeouts, optional reputation keys, minimal logging)

> **Important**: This is a starting point. It is designed so you can iterate quickly without breaking the contract.

## Quick start

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt

# Train baseline model (creates backend/models/artifacts/)
python scripts/train_text_model.py

# Run API
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open: http://localhost:5173

## How it works (high level)

1. **Text model** (baseline): word + char n-grams TF‑IDF + Logistic Regression, **calibrated**.
2. **URL intelligence**: parsing + canonicalization + look‑alike checks + safe redirect handling (no auto-follow by default).
3. **Policy guardrails**: deterministic rules that can *override* model uncertainty for high-risk patterns.
4. **Action guidance**: user-facing next steps (forward to 7726, type official domain, call number on back of card, etc.).

## Environment variables (optional)
Backend supports optional reputation providers. If unset, reputation is `"unknown"` and the system continues.

- `GOOGLE_SAFE_BROWSING_API_KEY`
- `VIRUSTOTAL_API_KEY`

## Repo layout
- `backend/app/` FastAPI service
- `backend/scripts/` training & evaluation
- `backend/models/` model registry + artifacts (artifacts are gitignored)
- `frontend/` Vite + React UI
- `shared/` shared contract/types

## Safety & ethics
This tool can be misused (e.g., to craft more convincing scams). Do not expose raw model outputs in a way that makes adversarial optimization easy.


### Optional reputation lookups (disabled by default)
By default, the backend **does not** make outbound network calls for privacy and safety.

To enable Google Safe Browsing and/or VirusTotal reputation checks:

1) Create `backend/.env` with:
```
ENABLE_REPUTATION_LOOKUPS=true
GOOGLE_SAFE_BROWSING_API_KEY=...
VIRUSTOTAL_API_KEY=...
```

2) Restart the backend.

Notes:
- Lookups are **best-effort** and **non-fatal** (timeouts/errors become `unknown`).
- URL reputation is combined conservatively: if any source flags malicious, the URL risk is forced high.
