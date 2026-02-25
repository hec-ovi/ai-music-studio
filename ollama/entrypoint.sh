#!/usr/bin/env bash
set -e

log() { echo "[ollama] $1"; }

# Start Ollama server in background
log "Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

# Cleanup on container exit
trap 'log "Shutting down..."; kill $OLLAMA_PID 2>/dev/null; exit 0' SIGTERM SIGINT

# Wait for server to be ready (up to 60s)
log "Waiting for Ollama to be ready..."
for i in $(seq 1 60); do
    if curl -sf http://localhost:11434/ > /dev/null 2>&1; then
        log "✓ Ollama server is ready"
        break
    fi
    if [ $i -eq 60 ]; then
        log "✗ Ollama failed to start within 60s"
        exit 1
    fi
    sleep 1
done

# Pull model if not present
MODEL="${OLLAMA_MODEL:-gpt-oss:20b}"
if ollama list | grep -q "^${MODEL}"; then
    log "✓ Model '${MODEL}' already present"
else
    log "⊘ Model '${MODEL}' not found — downloading..."
    ollama pull "${MODEL}"
    log "✓ Model '${MODEL}' ready"
fi

log "✓ Ready — model: ${MODEL}, context: ${OLLAMA_CONTEXT_LENGTH}, keep_alive: ${OLLAMA_KEEP_ALIVE}"

# Keep container alive
wait $OLLAMA_PID
