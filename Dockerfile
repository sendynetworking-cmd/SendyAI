FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for pypdf (if needed)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

ENV PYTHONPATH=/app
ENV PORT=8080

# Run the application
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"
