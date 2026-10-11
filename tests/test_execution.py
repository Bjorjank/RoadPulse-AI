"""Concurrency regressions using tiny byte payloads; no native ML/media imports."""

import importlib.util
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


profiles = load("test_profiles_module", "src/roadpulse/profiles.py")
export = load("test_export_module", "src/roadpulse/video/export.py")


class FakeProcess:
    def __init__(self, command, *, fail=False, gate=None, **kwargs):
        self.output = Path(command[-1])
        self.progress = Path(command[command.index("-progress") + 1])
        self.returncode = None
        self.received = bytearray()
        self.fail = fail
        self.gate = gate
        self.entered = threading.Event()
        self.stdin = self

    def write(self, view):
        self.entered.set()
        if self.gate is not None:
            self.gate.wait(timeout=2)
        if self.fail or self.returncode is not None:
            self.returncode = 1
            raise BrokenPipeError("test failure")
        length = min(7, len(view))  # Deliberately exercise partial OS pipe writes.
        self.received.extend(view[:length])
        return length

    def close(self):
        if self.returncode is None:
            self.output.write_bytes(bytes(self.received))
            self.progress.write_text(f"frame={len(self.received) // 12}\nprogress=end\n")
            self.returncode = 0

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.returncode = -15
        if self.gate is not None:
            self.gate.set()

    kill = terminate


class ExecutionTests(unittest.TestCase):
    def test_standard_budget(self):
        self.assertEqual(profiles.execution_profile("standard", cpu_count=64).inference_threads, 1)

    def test_fast_budget_is_bounded(self):
        for count in (1, 2, 4, 64):
            profile = profiles.execution_profile("fast", cpu_count=count)
            self.assertIn(profile.inference_threads, (1, 2))
            self.assertEqual(profile.pending_frames, 2)
        self.assertEqual(profiles.execution_profile("fast", cpu_count=4).inference_threads, 2)

    def test_reject_unknown_mode(self):
        with self.assertRaises(ValueError):
            profiles.execution_profile("turbo")

    def test_command_has_no_rate_limit_or_intermediate(self):
        command = export.encoder_command("ffmpeg", "out.mp4", 65, 49, 30, "progress.txt")
        self.assertIn("pipe:0", command)
        self.assertNotIn("-readrate", command)
        self.assertNotIn("-re", command)
        self.assertIn("bgr24", command)
        self.assertEqual(command[command.index("-framerate") + 1], "30")
        self.assertIn("pad=ceil(iw/2)*2:ceil(ih/2)*2", command)

    def test_all_frames_ordered_in_both_modes_despite_partial_writes(self):
        payloads = [bytes([i]) * 12 for i in range(12)]
        outputs = []
        for mode in ("standard", "fast"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                writer = export.StreamingExporter(
                    "fake",
                    tmp,
                    2,
                    2,
                    30,
                    profiles.execution_profile(mode).pending_frames,
                    popen=FakeProcess,
                )
                try:
                    for payload in payloads:
                        writer.write(payload, lambda: False)
                    writer.finish(lambda: False)
                    outputs.append((Path(tmp) / "annotated.mp4").read_bytes())
                    self.assertEqual(writer.encoded_frames(), 12)
                    self.assertFalse((Path(tmp) / "annotated.partial.mp4").exists())
                finally:
                    writer.abort()
        self.assertEqual(outputs, [b"".join(payloads)] * 2)

    def test_cancel_while_queue_is_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = threading.Event()
            writer = export.StreamingExporter(
                "fake",
                tmp,
                2,
                2,
                30,
                1,
                popen=lambda *a, **kw: FakeProcess(*a, gate=gate, **kw),
            )
            try:
                writer.write(b"a" * 12, lambda: False)
                self.assertTrue(writer.proc.entered.wait(timeout=1))
                writer.write(b"b" * 12, lambda: False)
                checks = [0]

                def cancelled():
                    checks[0] += 1
                    return checks[0] >= 2

                with self.assertRaises(export.ExportCancelled):
                    writer.write(b"c" * 12, cancelled)
                self.assertFalse(writer.thread.is_alive())
                self.assertFalse((Path(tmp) / "annotated.mp4").exists())
            finally:
                writer.abort()

    def test_encoder_failure_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = export.StreamingExporter(
                "fake", tmp, 2, 2, 30, popen=lambda *a, **kw: FakeProcess(*a, fail=True, **kw)
            )
            try:
                writer.write(b"a" * 12, lambda: False)
                with self.assertRaises(RuntimeError):
                    writer.finish(lambda: False)
                self.assertFalse((Path(tmp) / "annotated.mp4").exists())
            finally:
                writer.abort()

    def test_unbounded_queue_is_rejected(self):
        with self.assertRaises(ValueError):
            export.StreamingExporter("fake", ".", 2, 2, 30, pending_frames=0)

    def test_encoder_frame_mismatch_is_not_published(self):
        class WrongCountProcess(FakeProcess):
            def close(self):
                super().close()
                self.progress.write_text("frame=0\nprogress=end\n")

        with tempfile.TemporaryDirectory() as tmp:
            writer = export.StreamingExporter("fake", tmp, 2, 2, 30, popen=WrongCountProcess)
            try:
                writer.write(b"a" * 12, lambda: False)
                with self.assertRaisesRegex(RuntimeError, "frame count differs"):
                    writer.finish(lambda: False)
                self.assertFalse((Path(tmp) / "annotated.mp4").exists())
            finally:
                writer.abort()

    def test_wrong_raw_frame_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = export.StreamingExporter("fake", tmp, 2, 2, 30, popen=FakeProcess)
            try:
                with self.assertRaises(ValueError):
                    writer.write(b"bad", lambda: False)
            finally:
                writer.abort()


if __name__ == "__main__":
    unittest.main()
