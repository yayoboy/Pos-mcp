import threading
import time

from PIL import Image

from pos_mcp.jobstore import JobStore


def _img() -> Image.Image:
    return Image.new("1", (384, 100), color=1)


def test_create_and_get():
    store = JobStore()
    job = store.create("text", {"content": "hi"}, _img())
    assert store.get(job.id) is job
    assert store.latest() is job


def test_confirm_signals_event():
    store = JobStore()
    job = store.create("text", {"content": "hi"}, _img())
    result = {"decision": None}

    def wait_for_decision():
        job.wait(timeout=2)
        result["decision"] = job.decision

    t = threading.Thread(target=wait_for_decision)
    t.start()
    time.sleep(0.05)
    assert store.confirm(job.id, {"content": "edited"})
    t.join(timeout=2)
    assert result["decision"] == "print"
    assert job.edited_params == {"content": "edited"}


def test_cancel_signals_event():
    store = JobStore()
    job = store.create("text", {"content": "hi"}, _img())
    assert store.cancel(job.id)
    assert job.decision == "cancel"
    assert job.wait(timeout=0.1)


def test_update_rerenders():
    store = JobStore()
    calls = []

    def rerender(params):
        calls.append(params)
        return _img()

    job = store.create("text", {"content": "hi"}, _img(), rerender=rerender)
    updated = store.update(job.id, {"content": "ciao"})
    assert updated is not None
    assert updated.params["content"] == "ciao"
    assert calls == [{"content": "ciao"}]


def test_listener_notified():
    store = JobStore()
    events = []
    store.subscribe(lambda jid, ev: events.append((jid, ev)))
    job = store.create("text", {"content": "hi"}, _img())
    store.confirm(job.id)
    assert ("created" in [e[1] for e in events])
    assert ("confirmed" in [e[1] for e in events])
