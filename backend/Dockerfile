FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app /app/app
COPY backend/models /app/models
COPY backend/scripts /app/scripts
COPY backend/data /app/data

EXPOSE 8000
CMD ["sh", "-c", "python scripts/train_text_model.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
