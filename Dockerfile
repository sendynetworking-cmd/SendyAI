FROM python:3.10-slim

# Install system dependencies for resume parsing
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLP data for resume-parser
RUN python -m spacy download en_core_web_sm
RUN python -m nltk.downloader stopwords \
    punkt \
    averaged_perceptron_tagger \
    universal_tagset \
    wordnet \
    brown \
    maxent_ne_chunker

# Copy application code
COPY . .

# Ensure the app directory is in PYTHONPATH
ENV PYTHONPATH=/app

# Expose port (Railway will override this with $PORT)
EXPOSE 8080

# Run the application using shell form to ensure $PORT expansion works correctly
# We use the list form with sh -c for better portability
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"
