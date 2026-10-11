import csv
import json
import platform
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
import psutil
from trackers import ByteTrackTracker

from roadpulse.analytics.crossing import LineCounter
from roadpulse.detection.yolox import CLASSES, Detector
from roadpulse.jobs.schemas import Results
from roadpulse.jobs.store import Store
from roadpulse.profiles import execution_profile
from roadpulse.video.completeness import decode_warning
from roadpulse.video.export import ExportCancelled, StreamingExporter

Cancelled = ExportCancelled


def process_job(root, job_id):
    cv2.setNumThreads(1)
    store = Store(root)
    cap, writer = None, None
    result = None
    folder = Path(root) / job_id
    try:
        job = store.get(job_id)
        if job["status"] == "CANCELLED":
            return
        profile = execution_profile(job.get("mode", "standard"))
        store.update(job_id, status="RUNNING", phase="INITIALIZING")
        start = time.perf_counter()
        detector = Detector(threads=profile.inference_threads)
        store.update(job_id, provider=detector.provider)
        tracker = ByteTrackTracker(
            frame_rate=job["fps"], track_activation_threshold=0.3, high_conf_det_threshold=0.3
        )
        counter = LineCounter(job["line"], job["width"], job["height"])
        cap = cv2.VideoCapture(str(folder / "input.mp4"), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1])
        if not cap.isOpened():
            raise ValueError("Cannot reopen uploaded video")
        writer = StreamingExporter(
            imageio_ffmpeg.get_ffmpeg_exe(),
            folder,
            job["width"],
            job["height"],
            job["fps"],
            pending_frames=profile.pending_frames,
        )
        store.update(job_id, phase="ANALYZING")
        last_cancel_check, last_progress = 0.0, 0.0
        is_cancelled = False
        process = psutil.Process()

        def cancelled():
            nonlocal last_cancel_check, is_cancelled
            now = time.perf_counter()
            if now - last_cancel_check >= 0.25:
                is_cancelled = store.get(job_id)["status"] == "CANCELLED"
                last_cancel_check = now
            return is_cancelled

        def publish_progress(force=False, phase="ANALYZING"):
            nonlocal last_progress, peak
            now = time.perf_counter()
            if not force and now - last_progress < 0.5:
                return
            if cancelled():
                raise Cancelled()
            exported = writer.encoded_frames()
            denominator = max(job["total_frames"], frames, 1)
            peak = max(peak, process.memory_info().rss)
            store.update(
                job_id,
                processed_frames=frames,
                exported_frames=exported,
                phase=phase,
                progress=min(0.99, 0.90 * frames / denominator + 0.09 * exported / denominator),
            )
            last_progress = now

        latencies, volume, trails = [], Counter(), defaultdict(lambda: deque(maxlen=30))
        peak, write_time, processing_time, observations, frames = 0, 0.0, 0.0, 0, 0
        with (folder / "events.csv").open("w", newline="", encoding="utf-8") as output:
            csv_writer = csv.DictWriter(
                output, fieldnames=["track_id", "category", "direction", "frame", "video_seconds"]
            )
            csv_writer.writeheader()
            while True:
                if cancelled():
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
                writer.write(frame.tobytes(), cancelled)
                write_time += time.perf_counter() - write_start
                frames += 1
                publish_progress()
                if frames % 10 == 0:
                    output.flush()
        cap.release()
        cap = None
        warning = decode_warning(frames, job["total_frames"])
        if store.get(job_id)["status"] == "CANCELLED":
            raise Cancelled()
        elapsed = time.perf_counter() - start
        result = {
            "job_id": job_id,
            "model": "YOLOX-Tiny",
            "mode": profile.name,
            "inference_threads": profile.inference_threads,
            "provider": detector.provider,
            "provider_warnings": detector.failures,
            "frames_processed": frames,
            "reported_frames": job["total_frames"],
            "export_complete": False,
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
        # Retain genuine analytics before finalizing the encoder. An export failure
        # must not discard counts that were already computed successfully.
        (folder / "analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        store.update(job_id, results=result, phase="FINALIZING", error=warning)
        publish_progress(force=True, phase="FINALIZING")
        finalize_start = time.perf_counter()
        writer.finish(cancelled, lambda: publish_progress(phase="FINALIZING"))
        writer = None
        result["export_complete"] = True
        result["metrics"]["output_writing_seconds"] += time.perf_counter() - finalize_start
        result["metrics"]["elapsed_seconds"] = time.perf_counter() - start
        result["metrics"]["processing_fps"] = frames / result["metrics"]["elapsed_seconds"]
        Results.model_validate(result)
        (folder / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if store.get(job_id)["status"] == "CANCELLED":
            raise Cancelled()
        store.update(
            job_id,
            status="COMPLETED",
            phase="COMPLETED",
            results=result,
            processed_frames=frames,
            exported_frames=frames,
            progress=1.0,
            error=warning,
        )
    except Cancelled:
        if store.get(job_id)["status"] != "CANCELLED":
            store.update(job_id, status="CANCELLED", phase="CANCELLED")
    except Exception as exc:
        if store.get(job_id)["status"] not in {"CANCELLED", "COMPLETED"}:
            message = str(exc)
            if result is not None:
                message += ". Analysis is retained; CSV and analysis JSON are available."
            store.update(job_id, status="FAILED", phase="FAILED", error=message, results=result)
    finally:
        if cap is not None:
            cap.release()
        if writer is not None:
            writer.abort()
        if store.get(job_id)["status"] != "COMPLETED":
            for name in ("annotated.mp4", "annotated.partial.mp4", "intermediate.mp4", "summary.json"):
                (folder / name).unlink(missing_ok=True)
