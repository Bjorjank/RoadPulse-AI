import importlib.metadata
import json
import platform
import shutil
import sys
from pathlib import Path

import onnxruntime as ort

from roadpulse.config import MODEL
from roadpulse.detection.yolox import Detector


def main():
    packages = (
        "onnxruntime",
        "onnx",
        "opencv-python",
        "numpy",
        "trackers",
        "supervision",
        "fastapi",
        "pydantic",
    )
    report = {
        "python": sys.version,
        "os": platform.platform(),
        "machine": platform.machine(),
        "node": shutil.which("node"),
        "available_providers": ort.get_available_providers(),
        "model_present": MODEL.exists(),
        "packages": {p: importlib.metadata.version(p) for p in packages},
    }
    if MODEL.exists():
        detector = Detector()
        report.update(
            selected_provider=detector.provider,
            provider_warnings=detector.failures,
            initialization_seconds=detector.initialization_seconds,
            manifest=json.loads(MODEL.with_suffix(".json").read_text()),
        )
    print(json.dumps(report, indent=2))
    if not MODEL.exists():
        raise SystemExit("Model missing: run python scripts/prepare_model.py")
    if not Path("apps/web/node_modules/next/package.json").exists():
        raise SystemExit("Frontend missing: run setup from project root")


if __name__ == "__main__":
    main()
