"""Tiny actual codec check; no model loading, traffic claims or performance benchmark."""

import json
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg

from roadpulse.config import ROOT
from roadpulse.video.export import StreamingExporter


def main():
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    reports, checks = [], []
    with tempfile.TemporaryDirectory(dir=ROOT / "artifacts", prefix="tiny-encoder-") as temporary:
        root = Path(temporary)
        for mode, slots in [("standard", 1), ("fast", 2)]:
            folder = root / mode
            folder.mkdir()
            writer = StreamingExporter(executable, folder, 64, 48, 10, slots)
            try:
                for index in range(6):
                    writer.write(bytes([index * 20, 80, 160]) * (64 * 48), lambda: False)
                writer.finish(lambda: False)
                command = [
                    executable,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-threads",
                    "1",
                    "-i",
                    str(folder / "annotated.mp4"),
                    "-threads",
                    "1",
                    "-f",
                    "framemd5",
                    "pipe:1",
                ]
                decoded = subprocess.run(command, capture_output=True, text=True, timeout=15, check=True)
                frames = [line for line in decoded.stdout.splitlines() if line and not line.startswith("#")]
                if len(frames) != 6:
                    raise RuntimeError(f"{mode}: expected six decoded export frames")
                checks.append(frames)
                reports.append(
                    {
                        "mode": mode,
                        "pending_frames": slots,
                        "decoded_export_frames": len(frames),
                        "encoded_progress_frames": writer.encoded_frames(),
                        "output_bytes": (folder / "annotated.mp4").stat().st_size,
                    }
                )
            finally:
                writer.abort()
    if checks[0] != checks[1]:
        raise RuntimeError("Encoded frame hashes/order differ between modes")
    evidence = {
        "test": "six synthetic 64x48 frames; codec integration only, not traffic accuracy or speed evidence",
        "pass": True,
        "same_decoded_frames_and_order": True,
        "modes": reports,
        "model_loaded": False,
        "encoder_threads": 1,
    }
    (ROOT / "artifacts/mode-export-smoke.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()
