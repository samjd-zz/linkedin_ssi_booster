# --- STAGE 1: CORE (Lightweight) ---
FROM nvidia/cuda:13.0.1-runtime-ubuntu22.04 AS core_base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3-pip python3.11-dev \
    curl ca-certificates gnupg \
    libportaudio2 libgl1 libglib2.0-0 \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Fix the links immediately
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

WORKDIR /app
COPY requirements-core.txt .

# Use 'python -m pip' to guarantee it installs for the 3.11 engine
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements-core.txt && \
    python -m pip install spacy && \
    python -m spacy download en_core_web_md

COPY . .
RUN mkdir -p data/avatar data/selection yt-vid-data

CMD ["python", "main.py", "--console"]

# --- STAGE 2: FULL (The CPU Slammer) ---
FROM nvidia/cuda:13.0.1-devel-ubuntu22.04 AS full_build
WORKDIR /app

# 1. Build Tools + Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build build-essential \
    python3.11 python3-pip python3.11-dev \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# 2. Setup Linker and Heavy Build (STAY CACHED)
RUN ln -s /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/stubs/libcuda.so.1
ENV FORCE_CMAKE=1
ENV CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_LIBRARY_PATH=/usr/local/cuda/lib64/stubs"
ENV LIBRARY_PATH=/usr/local/cuda/lib64/stubs:${LIBRARY_PATH}
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64/stubs:${LD_LIBRARY_PATH}

RUN MAX_JOBS=4 pip install --no-cache-dir llama-cpp-python

# 3. NOW install the core requirements in this stage
# We copy ONLY the requirements file first to keep caching efficient
COPY requirements-flux.txt .
RUN pip install --no-cache-dir -r requirements-flux.txt

# 4. Finally bring in the code
COPY . .

CMD ["python", "main.py", "--full-mode"]