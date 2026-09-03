# --- STAGE 1: CORE (Lightweight) ---
FROM nvidia/cuda:13.2.0-runtime-ubuntu22.04 AS core_base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Add deadsnakes PPA to properly get python3.11 and its dedicated pip/venv on Ubuntu 22.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common curl ca-certificates gnupg \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-distutils python3.11-dev \
    libportaudio2 libgl1 libglib2.0-0 libpulse0 libasound2-plugins pulseaudio-utils \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && npx -y playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Install a clean, dedicated pip for Python 3.11
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Strictly link global commands to 3.11
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/local/bin/pip3.11 /usr/bin/pip

WORKDIR /app
COPY requirements-core.txt .

RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements-core.txt && \
    python -m spacy download en_core_web_md && \
    python -m spacy download ja_core_news_md

COPY . .
RUN mkdir -p data/avatar data/selection yt-vid-data

CMD ["python", "main.py", "--console"]

# --- STAGE 2: FULL (The CPU Slammer) ---
FROM nvidia/cuda:13.2.0-devel-ubuntu22.04 AS full_build
WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 1. Build Tools + Python 3.11 via deadsnakes
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common curl \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build build-essential \
    python3.11 python3.11-distutils python3.11-dev \
    && rm -rf /var/lib/apt/lists/*

# Install native pip for 3.11
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Enforce clean alternatives targeting python3.11 explicitly
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/local/bin/pip3.11 1

# 2. Setup Linker and Heavy Build (STAY CACHED)
# NOTE: the CUDA `stubs` directory provides a link-time-only libcuda.so used to
# compile llama-cpp-python. It must NOT leak into the runtime LD_LIBRARY_PATH —
# otherwise torch loads the stub instead of the real driver-injected libcuda and
# reports "CUDA driver is a stub library" (torch.cuda.is_available() == False).
# We therefore set LIBRARY_PATH (used by the linker `ld`) globally, but pass the
# stub LD_LIBRARY_PATH inline to the build command only.
RUN ln -s /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/stubs/libcuda.so.1
ENV FORCE_CMAKE=1
ENV CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_LIBRARY_PATH=/usr/local/cuda/lib64/stubs"
ENV LIBRARY_PATH=/usr/local/cuda/lib64/stubs:${LIBRARY_PATH}

# Build llama-cpp-python safely using isolated 3.11 environment.
# The stub libcuda is only on LD_LIBRARY_PATH for this single build command.
RUN MAX_JOBS=4 LD_LIBRARY_PATH=/usr/local/cuda/lib64/stubs:${LD_LIBRARY_PATH} \
    python -m pip install --no-cache-dir llama-cpp-python

# Ensure the runtime loader resolves the real driver libcuda (injected by the
# NVIDIA container runtime), never the build stub.
ENV LD_LIBRARY_PATH=/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/cuda/lib64

# 3. Cache optimizations for your remaining layers
COPY requirements-flux.txt .
RUN python -m pip install --no-cache-dir --ignore-installed flask && \
    python -m pip install --no-cache-dir -r requirements-flux.txt

# 4. Finally bring in the application code
COPY . .

CMD ["python", "flux_server.py"]