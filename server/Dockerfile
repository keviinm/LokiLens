# Use official Python image
FROM python:3.11-slim

WORKDIR /app

COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server/app.py ./
COPY server/s3_operations.py ./
COPY server/log_processor.py ./
COPY server/templates ./templates
COPY server/static ./static

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"] 