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
RUN python -m pip install spacy && python -m spacy download en_core_web_md

COPY . .
RUN mkdir -p data/avatar data/selection yt-vid-data

# This is what runs when you use the "core" target
CMD ["python", "main.py", "--console"]

# --- STAGE 2: FULL (The CPU Slammer) ---
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS full_build
WORKDIR /app

# 1. Build Tools + Python (The absolute essentials)
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build build-essential \
    python3.11 python3-pip python3.11-dev \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# 2. Setup Linker and RUN THE HEAVY BUILD NOW
# By doing this BEFORE copying libraries or code, this layer becomes "Frozen"
RUN ln -s /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/stubs/libcuda.so.1
ENV FORCE_CMAKE=1
ENV CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_LIBRARY_PATH=/usr/local/cuda/lib64/stubs"
ENV LIBRARY_PATH=/usr/local/cuda/lib64/stubs:${LIBRARY_PATH}
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64/stubs:${LD_LIBRARY_PATH}

RUN MAX_JOBS=4 pip install --no-cache-dir llama-cpp-python

# 3. NOW bring in the libraries and code from Stage 1
# Changes to your requirements.txt or main.py will only trigger these layers
COPY --from=core_base /usr/local/lib/python3.11/dist-packages /usr/local/lib/python3.11/dist-packages
COPY --from=core_base /app /app

CMD ["python", "main.py", "--full-mode"]