FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app
COPY models /app/models
COPY scripts /app/scripts
COPY data /app/data

EXPOSE 8000
CMD ["sh", "-c", "python scripts/train_text_model.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
