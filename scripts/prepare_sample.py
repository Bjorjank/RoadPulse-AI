"""Optional CC0 real traffic fixture. Media remains local and gitignored."""

import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
URL = "https://upload.wikimedia.org/wikipedia/commons/d/d4/Temporary_traffic_signal_at_Colonel_By_Drive.webm"
PAGE = "https://commons.wikimedia.org/wiki/File:Temporary_traffic_signal_at_Colonel_By_Drive.webm"


def main():
    source = ROOT / "data/sample-source.webm"
    target = ROOT / "data/sample-traffic.mp4"
    request = urllib.request.Request(URL, headers={"User-Agent": "RoadPulse-AI/0.1 local development"})
    with urllib.request.urlopen(request, timeout=120) as response, source.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-threads",
            "1",
            "-filter_threads",
            "1",
            "-readrate",
            "0.03",
            "-i",
            str(source),
            "-an",
            "-vf",
            "scale=960:-2",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(target),
        ],
        check=True,
    )
    manifest = {
        "author": "137a",
        "license": "CC0-1.0",
        "page": PAGE,
        "source": URL,
        "changes": "Full-duration video resized to 960px width, audio removed, H.264 MP4 conversion; no frame skipping",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "mp4_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    target.with_suffix(".json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
