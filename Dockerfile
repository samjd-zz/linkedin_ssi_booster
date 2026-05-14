# Use the devel image to ensure we have nvcc for llama-cpp-python
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies + Graphics libs for Flux
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3-pip python3.11-dev \
    build-essential cmake git curl \
    libportaudio2 portaudio19-dev \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

WORKDIR /app

# Install compiled GPU dependencies first (Caches this heavy layer)
ENV FORCE_CMAKE=1
ENV CMAKE_ARGS="-DGGML_CUDA=ON"
RUN pip install --no-cache-dir llama-cpp-python

# Install the rest from your specific requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# External model data
RUN python -m spacy download en_core_web_md

COPY . .
RUN mkdir -p data/avatar data/selection yt-vid-data models

CMD ["python", "main.py", "--help"]