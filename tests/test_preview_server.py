import base64

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from pos_mcp.jobstore import JobStore
from pos_mcp.preview_server import build_app
import pos_mcp.jobstore as jobstore_mod


@pytest.fixture
def fresh_store(monkeypatch):
    new = JobStore()
    monkeypatch.setattr(jobstore_mod, "_store", new)
    return new


@pytest.fixture
def client(fresh_store):
    app = build_app()
    return TestClient(app)


def _img() -> Image.Image:
    return Image.new("1", (384, 50), color=1)


def test_root_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>pos-mcp preview" in r.text.lower() or "preview" in r.text.lower()


def test_latest_empty(client):
    r = client.get("/api/jobs/latest")
    assert r.status_code == 200
    assert r.json()["job"] is None


def test_latest_returns_job(client, fresh_store):
    fresh_store.create("text", {"content": "hi"}, _img())
    r = client.get("/api/jobs/latest")
    assert r.status_code == 200
    job = r.json()["job"]
    assert job is not None
    assert job["kind"] == "text"
    assert base64.b64decode(job["png_b64"])


def test_confirm_endpoint(client, fresh_store):
    job = fresh_store.create("text", {"content": "hi"}, _img())
    r = client.post(f"/api/jobs/{job.id}/confirm", json={"content": "edited"})
    assert r.status_code == 200
    assert job.decision == "print"
    assert job.edited_params == {"content": "edited"}


def test_cancel_endpoint(client, fresh_store):
    job = fresh_store.create("text", {"content": "hi"}, _img())
    r = client.post(f"/api/jobs/{job.id}/cancel")
    assert r.status_code == 200
    assert job.decision == "cancel"


def test_update_endpoint(client, fresh_store):
    def rerender(params):
        return _img()

    job = fresh_store.create("text", {"content": "hi"}, _img(), rerender=rerender)
    r = client.post(f"/api/jobs/{job.id}/update", json={"content": "ciao"})
    assert r.status_code == 200
    assert r.json()["params"]["content"] == "ciao"


def test_unknown_job_404(client):
    r = client.post("/api/jobs/nope/confirm", json={})
    assert r.status_code == 404
