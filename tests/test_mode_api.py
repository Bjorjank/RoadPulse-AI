"""Mode persistence and retained downloads without native model/video imports."""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class Pool:
    def submit(self, *args):
        return SimpleNamespace(add_done_callback=lambda callback: None)

    def shutdown(self, **kwargs):
        pass


class ModeApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        import roadpulse.config as config
        from roadpulse.jobs.schemas import Job

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        model = root / "fixture-model.onnx"
        model.touch()
        spec = importlib.util.spec_from_file_location("mode_api_fixture", ROOT / "src/roadpulse/api.py")
        api = importlib.util.module_from_spec(spec)
        modules = {
            "cv2": SimpleNamespace(),
            "onnxruntime": SimpleNamespace(get_available_providers=lambda: ["fixture-only"]),
            "roadpulse.video.engine": SimpleNamespace(process_job=lambda *a: None),
        }
        with (
            patch.dict(sys.modules, modules),
            patch.object(config, "DATA", root),
            patch.object(config, "MODEL", model),
        ):
            spec.loader.exec_module(api)
        self.api = api
        app = api.create_app(root, enable_worker=False)
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        app.state.pool = Pool()
        self.store = app.state.store
        self.job_id = "a" * 32
        self.store.create(
            Job(
                id=self.job_id,
                filename="fixture.mp4",
                status="CREATED",
                width=64,
                height=48,
                fps=30,
                total_frames=6,
            ).model_dump(mode="json")
        )
        self.line = [{"x": 0.1, "y": 0.5}, {"x": 0.9, "y": 0.5}]

    def test_fast_is_persisted_and_returned(self):
        response = self.client.post(
            f"/api/jobs/{self.job_id}/start", json={"line": self.line, "mode": "fast"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["mode"], "fast")
        self.assertEqual(self.store.get(self.job_id)["mode"], "fast")
        self.assertEqual(response.json()["phase"], "QUEUED")

    def test_default_is_standard(self):
        response = self.client.post(f"/api/jobs/{self.job_id}/start", json={"line": self.line})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["mode"], "standard")

    def test_launcher_fast_default_works_with_old_frontend_request(self):
        from fastapi.testclient import TestClient

        with patch.dict(os.environ, {"ROADPULSE_DEFAULT_MODE": "fast"}):
            app = self.api.create_app(self.store.root, enable_worker=False)
        with TestClient(app) as client:
            app.state.pool = Pool()
            response = client.post(f"/api/jobs/{self.job_id}/start", json={"line": self.line})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["mode"], "fast")
            self.assertEqual(client.get("/api/system").json()["default_mode"], "fast")

    def test_invalid_mode_is_rejected_before_queue(self):
        response = self.client.post(
            f"/api/jobs/{self.job_id}/start", json={"line": self.line, "mode": "turbo"}
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.store.get(self.job_id)["status"], "CREATED")

    def test_system_advertises_modes(self):
        self.assertEqual(self.client.get("/api/system").json()["execution_modes"], ["standard", "fast"])

    def test_saved_history_and_inline_video_download(self):
        from roadpulse.jobs.schemas import Job

        older = self.job_id
        newer = "b" * 32
        self.store.create(
            Job(
                id=newer,
                filename="newer.mp4",
                status="CREATED",
                width=64,
                height=48,
                fps=30,
                total_frames=6,
            ).model_dump(mode="json")
        )
        listed = self.client.get("/api/jobs")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([j["id"] for j in listed.json()[:2]], [newer, older])

        folder = self.store.root / older
        folder.mkdir()
        payload = b"123456789"
        (folder / "annotated.mp4").write_bytes(payload)
        (folder / "events.csv").write_text("track_id,category\\n", encoding="utf-8")
        self.store.update(older, status="QUEUED")
        self.store.update(older, status="RUNNING")
        self.store.update(older, status="COMPLETED")
        video = self.client.get(f"/api/jobs/{older}/artifacts/annotated.mp4")
        self.assertEqual(video.status_code, 200)
        self.assertEqual(video.content, payload)
        self.assertTrue(video.headers["content-disposition"].startswith("inline;"))
        self.assertEqual(video.headers["cache-control"], "private, no-store")
        csv_response = self.client.get(f"/api/jobs/{older}/artifacts/events.csv")
        self.assertTrue(csv_response.headers["content-disposition"].startswith("attachment;"))

    def test_failed_results_remain_available(self):
        analysis = {
            "job_id": self.job_id, "model": "YOLOX-Tiny", "provider": "fixture",
            "provider_warnings": [], "frames_processed": 1, "tracked_observations": 1,
            "total": 0, "counts": {"car": 0}, "directions": {"A_TO_B": 0},
            "volume": [], "metrics": {
                "initialization_seconds": 0, "inference_average_ms": 1,
                "inference_median_ms": 1, "inference_p95_ms": 1,
                "model_only_fps": 1, "processing_fps": 1, "elapsed_seconds": 1,
                "frame_processing_seconds": 1, "output_writing_seconds": 0,
                "peak_ram_bytes": 1024, "os": "fixture", "cpu": "fixture",
            },
        }
        self.store.update(self.job_id, status="QUEUED")
        self.store.update(self.job_id, status="FAILED", results=analysis)
        response = self.client.get(f"/api/jobs/{self.job_id}/results")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["job_id"], self.job_id)
        self.assertEqual(response.json()["export_complete"], False)

    def test_failed_job_retained_analysis_allowlist(self):
        folder = self.store.root / self.job_id
        folder.mkdir()
        (folder / "events.csv").write_text("track_id,category\n7,car\n")
        (folder / "analysis.json").write_text('{"export_complete":false}')
        (folder / "annotated.mp4").write_bytes(b"incomplete")
        self.store.update(self.job_id, status="QUEUED")
        self.store.update(self.job_id, status="FAILED")
        for filename in ("events.csv", "analysis.json"):
            self.assertEqual(
                self.client.get(f"/api/jobs/{self.job_id}/artifacts/{filename}").status_code, 200
            )
        for filename in ("annotated.mp4", "input.mp4", "encode.log"):
            self.assertEqual(
                self.client.get(f"/api/jobs/{self.job_id}/artifacts/{filename}").status_code, 404
            )


if __name__ == "__main__":
    unittest.main()
