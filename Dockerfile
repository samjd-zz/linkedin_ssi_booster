FROM python:3.11-slim

# Install system dependencies needed by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    libportaudio2 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*   

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy English model (used by spacy_nlp.py)
RUN python -m spacy download en_core_web_md

# Copy application source
COPY . .

# Create runtime data directories in case they're not in the bind mount
RUN mkdir -p data/avatar data/selection yt-vid-data

# Default command — override via `docker compose run app python main.py --console`
CMD ["python", "main.py", "--help"]
