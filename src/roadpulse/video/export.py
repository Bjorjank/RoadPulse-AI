"""Bounded, ordered raw-frame streaming to a single H.264 encoder."""

import subprocess
import threading
from pathlib import Path
from queue import Empty, Full, Queue


class ExportCancelled(Exception):
    pass


def encoder_command(executable, output, width, height, fps, progress):
    return [
        str(executable),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-threads",
        "1",
        "-filter_threads",
        "1",
        "-f",
        "rawvideo",
        "-pixel_format",
        "bgr24",
        "-video_size",
        f"{width}x{height}",
        "-framerate",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-threads",
        "1",
        "-preset",
        "ultrafast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-fps_mode",
        "passthrough",
        "-movflags",
        "+faststart",
        "-progress",
        str(progress),
        "-stats_period",
        "0.5",
        str(output),
    ]


class StreamingExporter:
    def __init__(self, executable, folder, width, height, fps, pending_frames=1, *, popen=subprocess.Popen):
        if pending_frames not in (1, 2):
            raise ValueError("Export queue must contain one or two pending frames")
        self.folder = Path(folder)
        self.output = self.folder / "annotated.partial.mp4"
        self.progress_path = self.folder / "encode-progress.txt"
        self.expected_bytes = width * height * 3
        self.queue = Queue(maxsize=pending_frames)
        self.error = None
        self.aborted = threading.Event()
        self.submitted = 0
        self.log = (self.folder / "encode.log").open("wb")
        self.progress_path.unlink(missing_ok=True)
        try:
            self.proc = popen(
                encoder_command(executable, self.output, width, height, fps, self.progress_path),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=self.log,
                bufsize=0,
            )
        except BaseException:
            self.log.close()
            raise
        self.thread = threading.Thread(target=self._pump, name="roadpulse-export", daemon=True)
        self.thread.start()

    def _pump(self):
        try:
            while not self.aborted.is_set():
                try:
                    payload = self.queue.get(timeout=0.1)
                except Empty:
                    continue
                if payload is None:
                    break
                view = memoryview(payload)
                while len(view) and not self.aborted.is_set():
                    written = self.proc.stdin.write(view[:65536])
                    if not written:
                        raise BrokenPipeError("H.264 encoder pipe closed")
                    view = view[written:]
        except Exception as exc:
            self.error = exc
        finally:
            try:
                self.proc.stdin.close()
            except OSError:
                pass

    def _check(self, cancelled):
        if cancelled():
            self.abort()
            raise ExportCancelled()
        if self.error:
            raise RuntimeError("H.264 export failed; inspect encode.log") from self.error
        if self.proc.poll() not in (None, 0):
            raise RuntimeError("H.264 encoder exited; inspect encode.log")

    def _put(self, payload, cancelled):
        while True:
            self._check(cancelled)
            try:
                self.queue.put(payload, timeout=0.1)
                return
            except Full:
                pass

    def write(self, payload, cancelled):
        if len(payload) != self.expected_bytes:
            raise ValueError("Unexpected raw frame size")
        self._put(payload, cancelled)
        self.submitted += 1

    def encoded_frames(self):
        try:
            with self.progress_path.open("rb") as stream:
                stream.seek(0, 2)
                size = stream.tell()
                stream.seek(max(0, size - 4096))
                lines = stream.read().decode("ascii", errors="ignore").splitlines()
            values = [int(line[6:]) for line in lines if line.startswith("frame=") and line[6:].isdigit()]
            return max(values, default=0)
        except OSError:
            return 0

    def finish(self, cancelled, on_progress=lambda: None):
        self._put(None, cancelled)
        while self.thread.is_alive():
            self._check(cancelled)
            on_progress()
            self.thread.join(timeout=0.1)
        self._check(cancelled)
        while self.proc.poll() is None:
            self._check(cancelled)
            on_progress()
            try:
                self.proc.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass
        self._check(cancelled)
        self.log.close()
        if not self.output.is_file() or not self.output.stat().st_size:
            raise RuntimeError("H.264 encoder produced no output")
        if self.encoded_frames() != self.submitted:
            raise RuntimeError("H.264 export frame count differs from submitted analysis frames")
        self.output.replace(self.folder / "annotated.mp4")

    def abort(self):
        self.aborted.set()
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)
        self.thread.join(timeout=2)
        self.log.close()
        self.output.unlink(missing_ok=True)
