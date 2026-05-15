# --- STAGE 1: CORE (Lightweight) ---
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS core_base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3-pip python3.11-dev \
    libportaudio2 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_md

COPY . .
RUN mkdir -p data/avatar data/selection yt-vid-data

# This is what runs when you use the "core" target
CMD ["python", "main.py", "--console"]

# --- STAGE 2: FULL (The CPU Slammer) ---
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS full_build
WORKDIR /app

# 1. Build Tools
RUN apt-get update && apt-get install -y cmake ninja-build build-essential && rm -rf /var/lib/apt/lists/*

# 2. CUDA Linker Stubs
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64/stubs:${LD_LIBRARY_PATH}
ENV CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_LIBRARY_PATH=/usr/local/cuda/lib64/stubs"
ENV FORCE_CMAKE=1

# 3. The Heavy Lift (Cached)
# ⚠️ "Heavy Lift" - CPU 🔥 burn for llama-cpp-python with CUDA support ⚠️
RUN MAX_JOBS=4 pip install --no-cache-dir llama-cpp-python

# 4. Bring in the rest of the app from Stage 1
COPY --from=core_base /app /app

# This is what runs when you use the "full" target
CMD ["python", "main.py", "--full-mode"]