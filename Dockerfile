# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies in a single layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Install the local package in development mode
RUN pip install -e .

# Create logs directory
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Expose the ports the apps run on
EXPOSE 8000
EXPOSE 9000

# Command to run the application (commented out to allow Render to use startCommand)
# CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/app.py", "--reload-dir", "/app/s3_operations.py", "--reload-dir", "/app/log_processor.py"] 