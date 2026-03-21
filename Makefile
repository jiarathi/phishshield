.PHONY: backend frontend train test

backend:
	cd backend && uvicorn app.main:app --reload

frontend:
	cd frontend && npm run dev

train:
	cd backend && python scripts/train_text_model.py

test:
	cd backend && pytest -q
