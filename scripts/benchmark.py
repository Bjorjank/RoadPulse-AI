"""Real complete-video pipeline benchmark; never synthesizes performance results."""

import argparse
import json
import shutil
import uuid
from pathlib import Path

import cv2

from roadpulse.config import ROOT
from roadpulse.jobs.store import Store
from roadpulse.video.engine import process_job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument(
        "--line", nargs=4, type=float, default=[0.1, 0.5, 0.9, 0.5], metavar=("X1", "Y1", "X2", "Y2")
    )
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/benchmark.json")
    args = parser.parse_args()
    from roadpulse.jobs.schemas import StartRequest

    config = StartRequest(
        line=[{"x": args.line[0], "y": args.line[1]}, {"x": args.line[2], "y": args.line[3]}]
    )
    root = ROOT / "artifacts/benchmark-jobs"
    store = Store(root)
    job_id = uuid.uuid4().hex
    folder = root / job_id
    folder.mkdir()
    shutil.copyfile(args.video, folder / "input.mp4")
    cap = cv2.VideoCapture(str(args.video))
    try:
        ok, frame = cap.read()
        if not ok:
            raise SystemExit("Cannot decode input video")
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps > 0:
            raise SystemExit("Invalid FPS")
        job = {
            "id": job_id,
            "filename": args.video.name,
            "status": "CREATED",
            "width": frame.shape[1],
            "height": frame.shape[0],
            "fps": fps,
            "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "processed_frames": 0,
            "progress": 0,
            "error": None,
            "results": None,
        }
    finally:
        cap.release()
    store.create(job)
    store.update(job_id, status="QUEUED", line=[[p.x, p.y] for p in config.line], trails=True)
    process_job(root, job_id)
    job = store.get(job_id)
    if job["status"] != "COMPLETED":
        raise SystemExit(json.dumps(job))
    report = {
        "video": args.video.name,
        "resolution": [job["width"], job["height"]],
        "input_fps": fps,
        "artifacts_directory": str(folder),
        "line": args.line,
        **job["results"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
