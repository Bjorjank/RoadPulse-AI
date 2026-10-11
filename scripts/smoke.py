"""Execute real model + spawned API worker on a contiguous real-video excerpt."""

import argparse
import csv
import io
import json
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import cv2
import httpx
import numpy as np
from fastapi.testclient import TestClient

from roadpulse.api import create_app
from roadpulse.config import ROOT
from roadpulse.detection.yolox import Detector
from roadpulse.jobs.schemas import Results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--frames", type=int, default=180)
    parser.add_argument(
        "--url", help="Use a running local frontend/API instead of a temporary TestClient server"
    )
    args = parser.parse_args()
    if args.url:
        parsed = urlparse(args.url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise SystemExit("Smoke-test URL must be a local HTTP service")
    if args.frames < 2:
        raise SystemExit("Use at least two frames")
    with tempfile.TemporaryDirectory(prefix="smoke-", dir=ROOT / "artifacts") as tmp:
        root = Path(tmp)
        cap = cv2.VideoCapture(str(args.video))
        ok, frame = cap.read()
        if not ok:
            raise SystemExit("Real video cannot be opened")
        detector = Detector()
        detections, _ = detector.infer(frame)
        assert len(detections) > 0, "No real vehicle detections on first frame"
        assert np.isfinite(detections.xyxy).all()
        fps = cap.get(cv2.CAP_PROP_FPS)
        clip = root / "clip.mp4"
        writer = cv2.VideoWriter(
            str(clip), cv2.VideoWriter_fourcc(*"mp4v"), fps, (frame.shape[1], frame.shape[0])
        )
        assert writer.isOpened()
        count = 0
        try:
            while ok and count < args.frames:
                writer.write(frame)
                count += 1
                ok, frame = cap.read()
        finally:
            writer.release()
            cap.release()
        context = (
            httpx.Client(base_url=args.url, timeout=60) if args.url else TestClient(create_app(root / "jobs"))
        )
        with context as client:
            assert client.get("/api/health").status_code == 200

            def upload():
                with clip.open("rb") as file:
                    response = client.post(
                        "/api/jobs", files={"file": ("real-traffic.mp4", file, "video/mp4")}
                    )
                assert response.status_code == 201, response.text
                return response.json()["id"]

            config = {"line": [{"x": 0.1, "y": 0.5}, {"x": 0.9, "y": 0.5}], "trails": True}
            job_id = upload()
            assert client.post(f"/api/jobs/{job_id}/start", json=config).status_code == 200
            deadline = time.monotonic() + 600
            observed = []
            while time.monotonic() < deadline:
                job = client.get(f"/api/jobs/{job_id}").json()
                observed.append(job["processed_frames"])
                if job["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                    break
                time.sleep(0.2)
            assert job["status"] == "COMPLETED", job
            assert job["processed_frames"] == count
            assert any(0 < n < count for n in observed), "No intermediate progress observed"
            response = client.get(f"/api/jobs/{job_id}/results")
            assert response.status_code == 200, response.text
            result = Results.model_validate(response.json())
            assert result.tracked_observations > 0
            events_response = client.get(f"/api/jobs/{job_id}/artifacts/events.csv")
            assert events_response.status_code == 200
            events = list(csv.DictReader(io.StringIO(events_response.text)))
            assert len(events) == result.total
            for category, total in result.counts.items():
                assert sum(e["category"] == category for e in events) == total
            for direction, total in result.directions.items():
                assert sum(e["direction"] == direction for e in events) == total
            summary = client.get(f"/api/jobs/{job_id}/artifacts/summary.json")
            assert summary.json() == response.json() == job["results"]
            mp4 = client.get(f"/api/jobs/{job_id}/artifacts/annotated.mp4")
            assert mp4.status_code == 200 and len(mp4.content) > 100
            exported = root / "export.mp4"
            exported.write_bytes(mp4.content)
            cap = cv2.VideoCapture(str(exported))
            readable = 0
            while cap.read()[0]:
                readable += 1
            cap.release()
            assert readable == count, (readable, count)
            assert client.get(f"/api/jobs/{job_id}/artifacts/input.mp4").status_code == 404
            cancel_id = upload()
            assert client.post(f"/api/jobs/{cancel_id}/start", json=config).status_code == 200
            while time.monotonic() < deadline:
                current = client.get(f"/api/jobs/{cancel_id}").json()
                if current["status"] == "RUNNING":
                    break
                time.sleep(0.1)
            assert current["status"] == "RUNNING", current
            assert client.post(f"/api/jobs/{cancel_id}/cancel").json()["status"] == "CANCELLED"
            assert client.get(f"/api/jobs/{cancel_id}/results").status_code == 409
            assert client.get(f"/api/jobs/{cancel_id}/artifacts/annotated.mp4").status_code == 404
            report = {
                "status": "PASS",
                "transport": args.url or "FastAPI TestClient with spawned process worker",
                "input": args.video.name,
                "frames": count,
                "provider": result.provider,
                "tracked_observations": result.tracked_observations,
                "crossings": result.total,
                "checks": [
                    "real inference",
                    "spawned worker",
                    "progress",
                    "SQLite",
                    "CSV/JSON/API agreement",
                    "readable full MP4",
                    "artifact allowlist",
                    "running cancellation",
                ],
            }
        (ROOT / ("artifacts/http-smoke.json" if args.url else "artifacts/api-smoke.json")).write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
