FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for pypdf (if needed)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm && \
    python -m nltk.downloader stopwords punkt averaged_perceptron_tagger universal_tagset wordnet brown maxent_ne_chunker

# Copy application code
COPY . .

ENV PYTHONPATH=/app
ENV PORT=8080

# Run the application
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"
