"""FastAPI sidecar that hosts the browser preview UI and approval API.

Runs in a daemon thread with its own asyncio loop so it can coexist with the
synchronous FastMCP stdio loop. Communicates with the MCP-side worker through
the shared JobStore — never directly.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from pos_mcp.jobstore import get_store

log = logging.getLogger(__name__)

_UI_PATH = Path(__file__).parent / "preview.html"


def build_app() -> FastAPI:
    store = get_store()

    connections: set[WebSocket] = set()
    state: dict = {"loop": None}

    def on_store_event(job_id: str, event: str) -> None:
        loop = state["loop"]
        if loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            broadcast({"job_id": job_id, "event": event}),
            loop,
        )

    async def broadcast(message: dict) -> None:
        stale: list[WebSocket] = []
        for ws in list(connections):
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            connections.discard(ws)

    store.subscribe(on_store_event)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        state["loop"] = asyncio.get_running_loop()
        yield
        state["loop"] = None

    app = FastAPI(title="pos-mcp preview", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        if not _UI_PATH.exists():
            return HTMLResponse("<h1>preview.html missing</h1>", status_code=500)
        return HTMLResponse(_UI_PATH.read_text(encoding="utf-8"))

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/api/jobs/latest")
    async def latest() -> JSONResponse:
        job = store.latest()
        if not job:
            return JSONResponse({"job": None})
        return JSONResponse({"job": _serialize(job)})

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str) -> JSONResponse:
        job = store.get(job_id)
        if not job:
            raise HTTPException(404)
        return JSONResponse(_serialize(job))

    @app.post("/api/jobs/{job_id}/update")
    async def update_job(job_id: str, payload: dict) -> JSONResponse:
        job = store.update(job_id, payload or {})
        if not job:
            raise HTTPException(404, "job missing or not editable")
        return JSONResponse(_serialize(job))

    @app.post("/api/jobs/{job_id}/confirm")
    async def confirm(job_id: str, payload: dict | None = None) -> JSONResponse:
        ok = store.confirm(job_id, payload or {})
        if not ok:
            raise HTTPException(404)
        return JSONResponse({"status": "ok"})

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel(job_id: str) -> JSONResponse:
        ok = store.cancel(job_id)
        if not ok:
            raise HTTPException(404)
        return JSONResponse({"status": "ok"})

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        connections.add(ws)
        latest_job = store.latest()
        if latest_job:
            await ws.send_json({"job_id": latest_job.id, "event": "hello"})
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            connections.discard(ws)

    return app


def _serialize(job) -> dict:
    return {
        "id": job.id,
        "kind": job.kind,
        "params": job.params,
        "png_b64": job.png_b64(),
        "decision": job.decision,
        "created_at": job.created_at,
        "editable": job.rerender is not None,
    }


_server_thread: threading.Thread | None = None
_started_event = threading.Event()


def start(host: str = "127.0.0.1", port: int = 7878, auto_open: bool = False) -> str:
    """Start the preview server in a daemon thread. Returns the base URL.

    Safe to call multiple times; subsequent calls are no-ops.
    """
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return f"http://{host}:{port}"

    app = build_app()
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)

    def run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            _started_event.set()
            loop.run_until_complete(server.serve())
        finally:
            loop.close()

    _server_thread = threading.Thread(target=run, name="pos-mcp-preview", daemon=True)
    _server_thread.start()
    _started_event.wait(timeout=3)

    url = f"http://{host}:{port}"
    if auto_open:
        try:
            webbrowser.open(url, new=2)
        except Exception as e:
            log.warning("Could not auto-open browser: %s", e)
    return url
