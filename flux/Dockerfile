# FLUX.2-klein-4B — ROCm TheRock / Strix Halo (gfx1151)
FROM ubuntu:25.10

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Pin Python 3.12 (ROCm wheels target 3.12)
RUN uv venv .venv --python 3.12
ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv"

# Install PyTorch for ROCm gfx1151
RUN uv pip install --pre torch torchvision \
    --index-url https://rocm.prereleases.amd.com/whl/gfx1151/

# Install diffusers and inference dependencies
RUN uv pip install \
    "git+https://github.com/huggingface/diffusers.git@aac94befce95f1842511cf13f43b2b60fa27b966" \
    "huggingface-hub<1.0" \
    "transformers<5" \
    accelerate \
    sentencepiece \
    protobuf \
    Pillow \
    "fastapi[standard]" \
    uvicorn

# ROCm / Strix Halo env
ENV HSA_OVERRIDE_GFX_VERSION=11.5.1 \
    HIP_VISIBLE_DEVICES=0 \
    AMD_SERIALIZE_KERNEL=0 \
    PYTORCH_HIP_ALLOC_CONF=expandable_segments:True \
    HF_HOME=/root/.cache/huggingface \
    FLUX_MODEL=black-forest-labs/FLUX.2-klein-4B

COPY src/ /app/src/

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -sf http://localhost:8002/health || exit 1

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]
