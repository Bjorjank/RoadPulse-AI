import csv
import json
import platform
import subprocess
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
import psutil
from trackers import ByteTrackTracker

from roadpulse.analytics.crossing import LineCounter
from roadpulse.budget import rest_after
from roadpulse.detection.yolox import CLASSES, Detector
from roadpulse.jobs.schemas import Results
from roadpulse.jobs.store import Store
from roadpulse.video.completeness import decode_warning


class Cancelled(Exception):
    pass


def process_job(root, job_id):
    cv2.setNumThreads(1)
    store = Store(root)
    cap, writer = None, None
    folder = Path(root) / job_id
    try:
        job = store.get(job_id)
        if job["status"] == "CANCELLED":
            return
        store.update(job_id, status="RUNNING")
        start = time.perf_counter()
        detector = Detector()
        store.update(job_id, provider=detector.provider)
        tracker = ByteTrackTracker(
            frame_rate=job["fps"], track_activation_threshold=0.3, high_conf_det_threshold=0.3
        )
        counter = LineCounter(job["line"], job["width"], job["height"])
        cap = cv2.VideoCapture(
            str(folder / "input.mp4"), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1]
        )
        if not cap.isOpened():
            raise ValueError("Cannot reopen uploaded video")
        writer = cv2.VideoWriter(
            str(folder / "intermediate.mp4"),
            cv2.VideoWriter_fourcc(*"mp4v"),
            job["fps"],
            (job["width"], job["height"]),
        )
        if not writer.isOpened():
            raise RuntimeError("MP4 encoder unavailable")
        latencies, volume, trails = [], Counter(), defaultdict(lambda: deque(maxlen=30))
        peak, write_time, processing_time, observations, frames = 0, 0.0, 0.0, 0, 0
        with (folder / "events.csv").open("w", newline="", encoding="utf-8") as output:
            csv_writer = csv.DictWriter(
                output, fieldnames=["track_id", "category", "direction", "frame", "video_seconds"]
            )
            csv_writer.writeheader()
            while True:
                if frames % 10 == 0 and store.get(job_id)["status"] == "CANCELLED":
                    raise Cancelled()
                frame_start = time.perf_counter()
                ok, frame = cap.read()
                if not ok:
                    break
                detections, latency = detector.infer(frame)
                latencies.append(latency)
                tracked = tracker.update(detections)
                for box, category, track_id in zip(tracked.xyxy, tracked.class_id, tracked.tracker_id):
                    if track_id is None or int(track_id) < 0:
                        continue
                    observations += 1
                    x1, y1, x2, y2 = map(int, box)
                    point = ((x1 + x2) / 2, y2)
                    event = counter.update(int(track_id), CLASSES[int(category)], point, frames, job["fps"])
                    if event:
                        csv_writer.writerow(event)
                        volume[int(event["video_seconds"] // 10) * 10] += 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (90, 224, 90), 2)
                    cv2.putText(
                        frame,
                        f"{CLASSES[int(category)]} #{track_id}",
                        (x1, max(15, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (90, 224, 90),
                        1,
                    )
                    if job.get("trails", True):
                        trails[int(track_id)].append(tuple(map(int, point)))
                        pts = np.array(trails[int(track_id)], np.int32)
                        if len(pts) > 1:
                            cv2.polylines(frame, [pts], False, (255, 190, 70), 1)
                if frames % 100 == 0:
                    counter.prune(frames)
                    for key in list(trails):
                        if key not in counter.history:
                            del trails[key]
                cv2.line(frame, tuple(map(int, counter.a)), tuple(map(int, counter.b)), (0, 240, 255), 2)
                cv2.putText(
                    frame,
                    f"Crossings: {sum(counter.counts.values())}",
                    (18, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 240, 255),
                    2,
                )
                processing_time += time.perf_counter() - frame_start
                write_start = time.perf_counter()
                writer.write(frame)
                write_time += time.perf_counter() - write_start
                frames += 1
                peak = max(peak, psutil.Process().memory_info().rss)
                if frames % 10 == 0:
                    store.update(
                        job_id,
                        processed_frames=frames,
                        progress=min(0.98, frames / max(job["total_frames"], frames)),
                    )
                    output.flush()
                if not rest_after(
                    time.perf_counter() - frame_start,
                    lambda: store.get(job_id)["status"] == "CANCELLED",
                ):
                    raise Cancelled()
        cap.release()
        writer.release()
        cap, writer = None, None
        warning = decode_warning(frames, job["total_frames"])
        if store.get(job_id)["status"] == "CANCELLED":
            raise Cancelled()
        encode_start = time.perf_counter()
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-threads",
            "1",
            "-filter_threads",
            "1",
            "-readrate",
            str(min(1.0, 2.0 / job["fps"])),
            "-i",
            str(folder / "intermediate.mp4"),
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-movflags",
            "+faststart",
            str(folder / "annotated.mp4"),
        ]
        with (folder / "encode.log").open("wb") as log:
            proc = subprocess.Popen(command, stdout=log, stderr=log)
            while proc.poll() is None:
                if store.get(job_id)["status"] == "CANCELLED":
                    proc.terminate()
                    proc.wait()
                    raise Cancelled()
                time.sleep(0.1)
            if proc.returncode:
                raise RuntimeError("H.264 export failed; inspect this job's encode.log")
        write_time += time.perf_counter() - encode_start
        (folder / "intermediate.mp4").unlink(missing_ok=True)
        elapsed = time.perf_counter() - start
        result = {
            "job_id": job_id,
            "model": "YOLOX-Tiny",
            "provider": detector.provider,
            "provider_warnings": detector.failures,
            "frames_processed": frames,
            "reported_frames": job["total_frames"],
            "decode_warnings": [warning] if warning else [],
            "tracked_observations": observations,
            "total": sum(counter.counts.values()),
            "counts": {name: counter.counts[name] for name in CLASSES.values()},
            "directions": {name: counter.directions[name] for name in ("A_TO_B", "B_TO_A")},
            "volume": [
                {"seconds": t, "count": volume[t]} for t in range(0, int(frames / job["fps"]) + 1, 10)
            ],
            "metrics": {
                "initialization_seconds": detector.initialization_seconds,
                "inference_average_ms": float(np.mean(latencies) * 1000),
                "inference_median_ms": float(np.median(latencies) * 1000),
                "inference_p95_ms": float(np.percentile(latencies, 95) * 1000),
                "model_only_fps": frames / sum(latencies),
                "processing_fps": frames / elapsed,
                "elapsed_seconds": elapsed,
                "frame_processing_seconds": processing_time,
                "output_writing_seconds": write_time,
                "peak_ram_bytes": peak,
                "os": platform.platform(),
                "cpu": platform.processor(),
                "gpu": None,
            },
        }
        Results.model_validate(result)
        (folder / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if store.get(job_id)["status"] == "CANCELLED":
            raise Cancelled()
        # The existing built dashboard renders job.error, including this explicit
        # partial-result warning; no frontend rebuild is needed to make it visible.
        store.update(
            job_id, status="COMPLETED", results=result, processed_frames=frames,
            progress=1.0, error=warning,
        )
    except Cancelled:
        if store.get(job_id)["status"] != "CANCELLED":
            store.update(job_id, status="CANCELLED")
    except Exception as exc:
        if store.get(job_id)["status"] not in {"CANCELLED", "COMPLETED"}:
            store.update(job_id, status="FAILED", error=str(exc))
    finally:
        if cap is not None:
            cap.release()
        if writer is not None:
            writer.release()
        if store.get(job_id)["status"] != "COMPLETED":
            for name in ("annotated.mp4", "intermediate.mp4", "events.csv", "summary.json"):
                (folder / name).unlink(missing_ok=True)
