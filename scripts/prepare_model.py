"""Download only the official pre-exported YOLOX-Tiny ONNX release."""

import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx"


EXPECTED_SHA256 = "427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7"


def main():
    target = ROOT / "models/yolox_tiny.onnx"
    target.parent.mkdir(exist_ok=True)
    partial = target.with_suffix(".download")
    try:
        request = urllib.request.Request(
            "https://api.github.com/repos/Megvii-BaseDetection/YOLOX/releases/tags/0.1.1rc0",
            headers={"User-Agent": "RoadPulse-AI"},
        )
        metadata = json.load(urllib.request.urlopen(request, timeout=60))
        asset = next(a for a in metadata["assets"] if a["name"] == target.name)
        with urllib.request.urlopen(URL, timeout=120) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if partial.stat().st_size != asset["size"]:
            raise ValueError("Download length differs from official release metadata")
        digest = hashlib.sha256(partial.read_bytes()).hexdigest()
        if digest != EXPECTED_SHA256:
            raise ValueError("Model differs from the release hash pinned in this repository")
        published = asset.get("digest")
        if published and published != "sha256:" + digest:
            raise ValueError("Official SHA256 differs from download")
        onnx.checker.check_model(str(partial))
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(str(partial), sess_options=options, providers=["CPUExecutionProvider"])
        session.run(None, {session.get_inputs()[0].name: np.zeros((1, 3, 416, 416), np.float32)})
        partial.replace(target)
        manifest = {
            "model": "YOLOX-Tiny",
            "source": URL,
            "sha256": digest,
            "bytes": target.stat().st_size,
            "license": "Apache-2.0 (YOLOX repository)",
            "published_digest": published,
            "integrity_note": "Official release has no upstream digest when null; HTTPS source, release size, graph validation and local SHA256 recorded.",
        }
        target.with_suffix(".json").write_text(json.dumps(manifest, indent=2))
        print(json.dumps(manifest, indent=2))
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise SystemExit(f"Model preparation failed: {exc}") from exc


if __name__ == "__main__":
    main()
