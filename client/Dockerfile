# Use official Python image
FROM python:3.11-slim

WORKDIR /app

COPY client/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY client/mcp_client_api.py ./
COPY client/mcp_client.py ./

CMD ["uvicorn", "mcp_client_api:app", "--host", "0.0.0.0", "--port", "8001"] 