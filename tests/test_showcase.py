"""Lightweight packaging tests; never run AI or a native video encoder."""

import csv
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("showcase_script", ROOT / "scripts/prepare_showcase.py")
showcase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(showcase)


def fixture(tmp_path, *, event_count=1):
    folder = tmp_path / "data" / ("a" * 32)
    folder.mkdir(parents=True)
    with sqlite3.connect(tmp_path / "data/roadpulse.sqlite3") as db:
        db.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        record = {"id": "a" * 32, "filename": "demo.mp4", "status": "COMPLETED"}
        db.execute("INSERT INTO jobs VALUES (?, ?)", (record["id"], json.dumps(record)))
    video = b"\0\0\0\x18ftypisom" + bytes(2048)
    (folder / "annotated.mp4").write_bytes(video)
    rows = [
        {"track_id": "7", "category": "car", "direction": "A_TO_B", "frame": "1",
         "video_seconds": "0.1"}
    ][:event_count]
    with (folder / "events.csv").open("w", newline="") as output:
        writer = csv.DictWriter(
            output, fieldnames=["track_id", "category", "direction", "frame", "video_seconds"]
        )
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "job_id": "a" * 32, "export_complete": True,
        "model": "YOLOX-Tiny", "provider": "CPUExecutionProvider",
        "frames_processed": 5, "reported_frames": 5, "total": 1,
        "counts": {"car": 1, "motorcycle": 0, "bus": 0, "truck": 0},
        "directions": {"A_TO_B": 1, "B_TO_A": 0},
        "volume": [{"seconds": 0, "count": 1}], "decode_warnings": [],
    }
    (folder / "summary.json").write_text(json.dumps(summary))
    return video


def test_packaging_existing_demo(tmp_path, monkeypatch):
    original = fixture(tmp_path)
    monkeypatch.setattr(showcase, "PROJECT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["prepare_showcase.py"])
    monkeypatch.setattr(
        showcase, "run_ffmpeg", lambda args: Path(args[-1]).write_bytes(b"poster-frame")
    )
    showcase.main()
    out = tmp_path / "docs/showcase"
    assert (out / "roadpulse-demo.mp4").read_bytes() == original
    assert json.loads((out / "sample-summary.json").read_text())["total_crossings"] == 1
    assert "Faruk Yıldız" in (out / "MEDIA_PROVENANCE.md").read_text(encoding="utf-8")
    assert "track_id" in (out / "sample-events.csv").read_text()
    assert (out / "poster.jpg").exists()


def test_inconsistent_csv_blocks_publication(tmp_path, monkeypatch):
    fixture(tmp_path, event_count=0)
    monkeypatch.setattr(showcase, "PROJECT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["prepare_showcase.py"])
    with pytest.raises(SystemExit, match="CSV event rows disagree"):
        showcase.main()
    assert not (tmp_path / "docs/showcase/roadpulse-demo.mp4").exists()
