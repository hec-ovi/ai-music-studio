FROM ollama/ollama:rocm

RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV OLLAMA_MODEL=gpt-oss:20b \
    OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_CONTEXT_LENGTH=8192 \
    OLLAMA_FLASH_ATTENTION=1 \
    OLLAMA_KV_CACHE_TYPE=q8_0 \
    OLLAMA_KEEP_ALIVE=0 \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_MAX_LOADED_MODELS=1 \
    OLLAMA_MODELS=/ollama-models \
    HSA_OVERRIDE_GFX_VERSION=11.5.1 \
    HIP_VISIBLE_DEVICES=0 \
    AMD_SERIALIZE_KERNEL=0

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 11434

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD ollama list > /dev/null 2>&1 || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
