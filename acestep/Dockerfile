# ACE-Step 1.5 — ROCm TheRock / Strix Halo (gfx1151)
# Runs a lazy-loading proxy on :8001.
# The actual ACE-Step model is loaded ONLY on the first generation request.
FROM ubuntu:25.10

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    git-lfs \
    build-essential \
    ca-certificates \
    libgomp1 \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install UV (Rust-based Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Pin Python 3.12 (ROCm wheels target 3.12; system Python on Ubuntu Rolling is 3.13)
RUN uv venv .venv --python 3.12
ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv"

# Install PyTorch for ROCm gfx1151 from AMD prerelease wheel index
RUN uv pip install --pre torch torchvision torchaudio \
    --index-url https://rocm.prereleases.amd.com/whl/gfx1151/

# Install proxy dependencies (minimal — no model loaded at startup)
RUN uv pip install "fastapi[standard]" httpx uvicorn

# Clone ACE-Step 1.5 and install its dependencies
RUN git clone --depth=1 https://github.com/ace-step/ACE-Step-1.5.git /app/acestep
WORKDIR /app/acestep

# Install ACE-Step (ROCm variant; fallback to base install)
RUN uv pip install -e ".[rocm]" 2>/dev/null \
    || { uv pip install -e . && uv pip install -r requirements-rocm.txt 2>/dev/null || true; }

# ACE-Step dependency resolution can replace ROCm torch with CUDA wheels.
# Re-assert ROCm builds so runtime actually sees the AMD GPU.
RUN uv pip install --pre --force-reinstall torch torchvision torchaudio \
    --index-url https://rocm.prereleases.amd.com/whl/gfx1151/

WORKDIR /app

# ROCm / Strix Halo env
ENV HSA_OVERRIDE_GFX_VERSION=11.5.1 \
    HIP_VISIBLE_DEVICES=0 \
    AMD_SERIALIZE_KERNEL=0 \
    PYTORCH_HIP_ALLOC_CONF=expandable_segments:True \
    ACESTEP_CONFIG_PATH=acestep-v15-turbo \
    ACESTEP_LM_MODEL_PATH=acestep-5Hz-lm-1.7B \
    # Internal port for the actual ACE-Step server (only used after first request)
    ACESTEP_INTERNAL_PORT=8011 \
    PORT=8001 \
    HF_HOME=/root/.cache/huggingface

# Copy lazy-loading proxy
COPY src/ /app/src/

EXPOSE 8001

# Health check passes as soon as the proxy is up (no model loaded yet)
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8001/health || exit 1

# Run the lazy-loading proxy on :8001
CMD ["python", "-m", "uvicorn", "src.proxy:app", "--host", "0.0.0.0", "--port", "8001"]
