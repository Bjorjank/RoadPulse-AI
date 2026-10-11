"""Worker integration with deterministic fixtures; no native ML/video imports."""

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class Frame:
    def __init__(self, index):
        self.index = index

    def tobytes(self):
        return bytes([self.index % 256]) * 12


class Capture:
    def __init__(self, count):
        self.count, self.index, self.released = count, 0, False

    def isOpened(self):
        return True

    def read(self):
        if self.index >= self.count:
            return False, None
        frame = Frame(self.index)
        self.index += 1
        return True, frame

    def release(self):
        self.released = True


class Detector:
    provider = "fixture-only"
    failures = []
    initialization_seconds = 0.01

    def __init__(self, threads):
        self.threads = threads

    def infer(self, frame):
        return frame, 0.001


class Tracker:
    def __init__(self, **kwargs):
        pass

    def update(self, frame):
        # One fixture vehicle crosses the actual finite-line counter once.
        bottom = 15 if frame.index == 0 else 35
        return SimpleNamespace(xyxy=[[10, 5, 30, bottom]], class_id=[2], tracker_id=[7])


class Writer:
    fail_finish = False
    instances = []

    def __init__(self, executable, folder, width, height, fps, pending_frames):
        self.folder, self.payloads, self.aborted = Path(folder), [], False
        self.pending_frames = pending_frames
        self.__class__.instances.append(self)

    def write(self, payload, cancelled):
        self.payloads.append(payload)

    def encoded_frames(self):
        return len(self.payloads)

    def finish(self, cancelled, on_progress):
        if self.fail_finish:
            raise RuntimeError("Fixture encoder failure")
        on_progress()
        (self.folder / "annotated.mp4").write_bytes(b"fixture output, not a real video")

    def abort(self):
        self.aborted = True


class WorkerExecutionTests(unittest.TestCase):
    def run_fixture(self, mode, *, reported=3, decoded=3, fail_finish=False):
        from roadpulse.jobs.store import Store

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        folder = root / "fixture"
        folder.mkdir()
        store = Store(root)
        store.create(
            {
                "id": "fixture",
                "filename": "fixture.mp4",
                "status": "QUEUED",
                "width": 40,
                "height": 48,
                "fps": 30,
                "total_frames": reported,
                "line": [[0.1, 0.5], [0.9, 0.5]],
                "trails": False,
                "mode": mode,
            }
        )
        capture = Capture(decoded)
        cv = SimpleNamespace(
            setNumThreads=lambda _: None,
            VideoCapture=lambda *a: capture,
            CAP_FFMPEG=1,
            CAP_PROP_N_THREADS=2,
            FONT_HERSHEY_SIMPLEX=0,
            rectangle=lambda *a: None,
            putText=lambda *a: None,
            line=lambda *a: None,
        )
        np = SimpleNamespace(
            mean=lambda x: sum(x) / len(x),
            median=lambda x: x[len(x) // 2],
            percentile=lambda x, p: max(x),
        )
        modules = {
            "cv2": cv,
            "numpy": np,
            "imageio_ffmpeg": SimpleNamespace(get_ffmpeg_exe=lambda: "fixture"),
            "psutil": SimpleNamespace(
                Process=lambda: SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=1000))
            ),
            "trackers": SimpleNamespace(ByteTrackTracker=Tracker),
            "roadpulse.detection.yolox": SimpleNamespace(
                CLASSES={2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}, Detector=Detector
            ),
        }
        spec = importlib.util.spec_from_file_location(
            "worker_fixture", ROOT / "src/roadpulse/video/engine.py"
        )
        engine = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(engine)
            with (
                patch.object(engine, "StreamingExporter", Writer),
                patch.object(Writer, "fail_finish", fail_finish),
            ):
                engine.process_job(root, "fixture")
        self.assertTrue(capture.released)
        return store.get("fixture"), folder, Writer.instances[-1]

    def test_modes_preserve_count_and_order(self):
        payloads = []
        for mode in ("standard", "fast"):
            job, folder, writer = self.run_fixture(mode)
            self.assertEqual(job["status"], "COMPLETED", job.get("error"))
            self.assertEqual(job["results"]["counts"]["car"], 1)
            self.assertEqual(job["results"]["directions"]["A_TO_B"], 1)
            self.assertEqual(job["results"]["frames_processed"], 3)
            self.assertEqual(job["exported_frames"], 3)
            self.assertTrue(job["results"]["export_complete"])
            self.assertEqual(job["results"]["mode"], mode)
            payloads.append(writer.payloads)
        self.assertEqual(*payloads)

    def test_small_tail_gap_exports_with_warning(self):
        job, folder, writer = self.run_fixture("fast", reported=465, decoded=462)
        self.assertEqual(job["status"], "COMPLETED", job.get("error"))
        self.assertIn("462/465", job["error"])
        self.assertEqual(job["results"]["frames_processed"], 462)
        self.assertEqual(len(writer.payloads), 462)

    def test_export_failure_retains_analysis_and_csv(self):
        job, folder, writer = self.run_fixture("standard", fail_finish=True)
        self.assertEqual(job["status"], "FAILED")
        self.assertEqual(job["results"]["total"], 1)
        self.assertFalse(job["results"]["export_complete"])
        self.assertTrue((folder / "analysis.json").exists())
        self.assertEqual(json.loads((folder / "analysis.json").read_text())["total"], 1)
        with (folder / "events.csv").open() as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 1)
        self.assertFalse((folder / "annotated.mp4").exists())
        self.assertTrue(writer.aborted)

    def test_large_decode_gap_still_fails(self):
        job, folder, writer = self.run_fixture("standard", reported=465, decoded=20)
        self.assertEqual(job["status"], "FAILED")
        self.assertIn("20/465", job["error"])
        self.assertTrue(writer.aborted)

    def test_start_contract_default_and_rejection(self):
        from roadpulse.jobs.schemas import StartRequest

        line = [{"x": 0, "y": 0.5}, {"x": 1, "y": 0.5}]
        self.assertEqual(StartRequest(line=line).mode, "standard")
        self.assertEqual(StartRequest(line=line, mode="fast").mode, "fast")
        with self.assertRaises(ValueError):
            StartRequest(line=line, mode="turbo")


if __name__ == "__main__":
    unittest.main()
