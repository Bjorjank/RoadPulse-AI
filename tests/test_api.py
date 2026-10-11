import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from roadpulse.api import create_app
from roadpulse.jobs.store import Store


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "jobs", enable_worker=False)) as c:
        yield c


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "fixture.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    assert writer.isOpened()
    for _ in range(5):
        writer.write(np.zeros((48, 64, 3), np.uint8))
    writer.release()
    return path.read_bytes()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/system").json()["model"] == "YOLOX-Tiny"


def test_create_persist_cancel(client, video):
    response = client.post("/api/jobs", files={"file": ("fixture.mp4", video, "video/mp4")})
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["total_frames"] == 5
    assert Store(client.app.state.store.root).get(job["id"])["filename"] == "fixture.mp4"
    assert client.get(f"/api/jobs/{job['id']}/results").status_code == 409
    assert client.post(f"/api/jobs/{job['id']}/cancel").json()["status"] == "CANCELLED"
    assert (
        client.post(
            f"/api/jobs/{job['id']}/start", json={"line": [{"x": 0, "y": 0.5}, {"x": 1, "y": 0.5}]}
        ).status_code
        == 409
    )


@pytest.mark.parametrize("name,content", [("../evil.mp4", b"bad"), ("a.txt", b"bad"), ("a.mp4", b"bad")])
def test_bad_upload(client, name, content):
    assert client.post("/api/jobs", files={"file": (name, content)}).status_code == 400


def test_unknown_and_origin(client):
    assert client.get("/api/jobs/not-a-job").status_code == 404
    assert client.get("/api/health", headers={"Origin": "https://evil.example"}).status_code == 403


def test_transitions(tmp_path):
    store = Store(tmp_path)
    store.create({"id": "a", "status": "CREATED"})
    with pytest.raises(ValueError):
        store.update("a", status="COMPLETED")
    for state in ("QUEUED", "RUNNING", "COMPLETED"):
        store.update("a", status=state)
    with pytest.raises(ValueError):
        store.update("a", status="RUNNING")


def test_content_length_limit(client):
    response = client.post(
        "/api/jobs",
        content=b"",
        headers={"content-length": str(2 * 1024**3), "content-type": "multipart/form-data; boundary=test"},
    )
    assert response.status_code == 413


def test_actual_file_limit(client, video, monkeypatch):
    monkeypatch.setattr("roadpulse.api.MAX_UPLOAD", 64)
    response = client.post("/api/jobs", files={"file": ("fixture.mp4", video)})
    assert response.status_code == 413
    assert not list(client.app.state.store.root.glob("*/input.mp4"))
