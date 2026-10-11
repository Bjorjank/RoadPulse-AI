import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.getenv("ROADPULSE_DATA", str(ROOT / "data")))
MODEL = ROOT / "models" / "yolox_tiny.onnx"
MAX_UPLOAD = 1024 * 1024 * 1024
