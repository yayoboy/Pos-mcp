"""In-memory store for confirm-mode print jobs.

A job is created when an MCP tool runs in `mode="confirm"`. It holds the
rendered preview bitmap and the original parameters; the MCP tool blocks on
`event.wait(timeout)` until the browser POSTs a decision. The store is shared
between the MCP thread (sync) and the FastAPI thread (async) — operations are
guarded by a single Lock.
"""

from __future__ import annotations

import base64
import io
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from PIL import Image


@dataclass
class Job:
    id: str
    kind: str  # "text" | "image" | "diagram" | "barcode"
    params: dict[str, Any]
    image: Image.Image
    created_at: float = field(default_factory=time.time)
    decision: str | None = None  # "print" | "cancel"
    edited_params: dict[str, Any] | None = None
    rerender: Callable[[dict[str, Any]], Image.Image] | None = None
    _event: threading.Event = field(default_factory=threading.Event)

    def png_b64(self) -> str:
        buf = io.BytesIO()
        self.image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def wait(self, timeout: float) -> bool:
        return self._event.wait(timeout=timeout)

    def signal(self) -> None:
        self._event.set()


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._listeners: list[Callable[[str, str], None]] = []

    def create(
        self,
        kind: str,
        params: dict[str, Any],
        image: Image.Image,
        rerender: Callable[[dict[str, Any]], Image.Image] | None = None,
    ) -> Job:
        job = Job(
            id=uuid.uuid4().hex[:12],
            kind=kind,
            params=params,
            image=image,
            rerender=rerender,
        )
        with self._lock:
            self._jobs[job.id] = job
        self._notify(job.id, "created")
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def latest(self) -> Job | None:
        with self._lock:
            if not self._jobs:
                return None
            return max(self._jobs.values(), key=lambda j: j.created_at)

    def update(self, job_id: str, new_params: dict[str, Any]) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
        if not job or not job.rerender:
            return None
        merged = {**job.params, **new_params}
        job.image = job.rerender(merged)
        job.params = merged
        self._notify(job_id, "updated")
        return job

    def confirm(self, job_id: str, edits: dict[str, Any] | None = None) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            return False
        job.edited_params = edits or {}
        job.decision = "print"
        job.signal()
        self._notify(job_id, "confirmed")
        return True

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            return False
        job.decision = "cancel"
        job.signal()
        self._notify(job_id, "cancelled")
        return True

    def remove(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    def subscribe(self, listener: Callable[[str, str], None]) -> None:
        self._listeners.append(listener)

    def _notify(self, job_id: str, event: str) -> None:
        for listener in list(self._listeners):
            try:
                listener(job_id, event)
            except Exception:
                pass


_store: JobStore | None = None


def get_store() -> JobStore:
    global _store
    if _store is None:
        _store = JobStore()
    return _store
