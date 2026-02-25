"""ACE-Step lazy-loading proxy.

Starts the ACE-Step model server ONLY when the first generation request
arrives — ensuring zero GPU memory is used until music generation begins.

Flow:
  Container starts → proxy is up (health: OK, model: NOT loaded)
  Backend sends /release_task → proxy starts acestep-api subprocess on :8011
                              → waits for model to load (~60-180s)
                              → proxies request and all subsequent calls
"""

import asyncio
import logging
import os
import shutil
import subprocess
import sys

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

logging.basicConfig(level=logging.INFO, format="[proxy] %(message)s")
log = logging.getLogger("proxy")

app = FastAPI(title="ACE-Step Lazy Proxy", docs_url=None, redoc_url=None)

INTERNAL_PORT = int(os.getenv("ACESTEP_INTERNAL_PORT", "8011"))
INTERNAL_URL = f"http://127.0.0.1:{INTERNAL_PORT}"
MODEL = os.getenv("ACESTEP_CONFIG_PATH", "acestep-v15-turbo")

_ready = asyncio.Event()
_start_lock = asyncio.Lock()
_proc: asyncio.subprocess.Process | None = None


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    """Always returns 200 — model_loaded indicates whether inference is ready."""
    return {"status": "ok", "model_loaded": _ready.is_set()}


# ─── Transparent proxy ───────────────────────────────────────────────────────

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "HEAD"])
async def proxy_request(request: Request, path: str) -> Response:
    """Lazy-start ACE-Step, then proxy all requests to it."""
    await _ensure_running()

    url = f"{INTERNAL_URL}/{path}"
    body = await request.body()
    # Strip hop-by-hop headers that must not be forwarded
    skip = {"host", "content-length", "transfer-encoding", "connection"}
    headers = {k: v for k, v in request.headers.items() if k.lower() not in skip}

    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers=headers,
                params=dict(request.query_params),
            )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type"),
        )
    except httpx.ConnectError as exc:
        raise HTTPException(status_code=502, detail=f"ACE-Step internal error: {exc}") from exc


# ─── Lazy startup ────────────────────────────────────────────────────────────

async def _ensure_running() -> None:
    """Idempotent: start ACE-Step once, wait until ready."""
    if _ready.is_set():
        return
    async with _start_lock:
        if _ready.is_set():
            return
        log.info("First inference request — starting ACE-Step model server…")
        await _launch_acestep()


async def _launch_acestep() -> None:
    """Spawn acestep-api on the internal port and block until healthy."""
    global _proc

    cmd = _build_cmd()
    log.info(f"Command: {' '.join(cmd)}")

    env = os.environ.copy()
    env["PORT"] = str(INTERNAL_PORT)

    _proc = await asyncio.create_subprocess_exec(*cmd, env=env)
    log.info(f"ACE-Step process started (PID {_proc.pid}), waiting for model load…")

    for i in range(360):  # up to 6 minutes
        await asyncio.sleep(1)
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{INTERNAL_URL}/health")
                if resp.status_code == 200:
                    _ready.set()
                    log.info("✓ ACE-Step model server ready")
                    return
        except Exception:
            pass

        if i % 30 == 0 and i > 0:
            log.info(f"  …still loading ({i}s elapsed)")

    raise RuntimeError("ACE-Step failed to become ready within 6 minutes")


def _build_cmd() -> list[str]:
    """Return the command to start ACE-Step API server on the internal port."""
    if shutil.which("acestep-api"):
        base_cmd = ["acestep-api"]
    else:
        # Fallback: try as Python module
        base_cmd = [sys.executable, "-m", "acestep.api"]

    cmd = [*base_cmd, "--port", str(INTERNAL_PORT), "--host", "127.0.0.1"]
    help_text = _help_text(base_cmd)

    # ACE-Step CLI options changed across versions; only pass supported flags.
    if "--config_path" in help_text:
        cmd.extend(["--config_path", MODEL])
    elif "--config-path" in help_text:
        cmd.extend(["--config-path", MODEL])
    else:
        log.info("No config path flag detected; using ACE-Step default model selection.")

    lm_model = os.getenv("ACESTEP_LM_MODEL_PATH", "").strip()
    if lm_model:
        if "--lm-model-path" in help_text:
            cmd.extend(["--lm-model-path", lm_model])
        elif "--lm_model_path" in help_text:
            cmd.extend(["--lm_model_path", lm_model])

    return cmd


def _help_text(base_cmd: list[str]) -> str:
    """Return lowercased CLI --help text for capability detection."""
    try:
        proc = subprocess.run(  # noqa: S603
            [*base_cmd, "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return f"{proc.stdout}\n{proc.stderr}".lower()
    except Exception:
        return ""
