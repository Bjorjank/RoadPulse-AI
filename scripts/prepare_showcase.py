"""Package an EXISTING successful demo job for a GitHub portfolio showcase.

No model import, no detection rerun, no download or network access.
Optional --compress transcodes only the already-annotated MP4, using one thread.
"""

import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://www.pexels.com/video/busy-urban-highway-with-flowing-traffic-29607724/"
LIMIT_BYTES = 40 * 1024 * 1024


def fatal(message):
    raise SystemExit("SHOWCASE_BLOCKED: " + str(message))


def ffmpeg_binary():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, OSError) as exc:
        fatal("FFmpeg is unavailable in the project environment: " + str(exc))


def run_ffmpeg(arguments):
    result = subprocess.run(
        [ffmpeg_binary(), "-hide_banner", "-loglevel", "error", "-y", *arguments],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode:
        fatal("FFmpeg failed: " + result.stderr[-1200:])


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def get_demo_job(data):
    db_file = data / "roadpulse.sqlite3"
    if not db_file.is_file():
        fatal("No SQLite job database found: " + str(db_file))
    with sqlite3.connect(db_file) as db:
        records = db.execute("SELECT payload FROM jobs ORDER BY rowid DESC").fetchall()
    found = False
    for (payload,) in records:
        job = json.loads(payload)
        if Path(job.get("filename", "")).stem.casefold() == "demo":
            found = True
            if job.get("status") == "COMPLETED":
                return job
    if found:
        fatal("Found demo.mp4 jobs, but none completed successfully. Check their encoder logs.")
    fatal("No analyzed job named demo.mp4. Verify the filename in the dashboard.")


def validate(job, folder):
    if job["status"] != "COMPLETED":
        log_path = folder / "encode.log"
        lines = log_path.read_text(errors="replace").splitlines()[-15:] if log_path.exists() else []
        fatal("demo status=" + job["status"] + "; " + "\n".join(lines))
    video = folder / "annotated.mp4"
    csv_file = folder / "events.csv"
    summary_file = folder / "summary.json"
    if not all(p.is_file() for p in (video, csv_file, summary_file)):
        fatal("Completed job is missing annotated.mp4, events.csv or summary.json.")
    if video.stat().st_size < 1024:
        fatal("Annotated MP4 is unexpectedly small.")
    with video.open("rb") as stream:
        if stream.read(12)[4:8] != b"ftyp":
            fatal("Output does not have a recognizable MP4 header.")
    result = json.loads(summary_file.read_text(encoding="utf-8"))
    if result.get("job_id") != job["id"] or not result.get("export_complete"):
        fatal("Summary does not match the completed job / export.")
    with csv_file.open(newline="", encoding="utf-8") as stream:
        events = list(csv.DictReader(stream))
    if len(events) != result["total"]:
        fatal("CSV event rows disagree with JSON total.")
    categories = Counter(event["category"] for event in events)
    directions = Counter(event["direction"] for event in events)
    if any(categories[name] != count for name, count in result["counts"].items()):
        fatal("CSV categories disagree with JSON counts.")
    if any(directions[name] != count for name, count in result["directions"].items()):
        fatal("CSV directions disagree with JSON directions.")
    return video, csv_file, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compress", action="store_true",
        help="Opt in to a one-thread 960px/24fps transcode only if the existing MP4 is too large.",
    )
    args = parser.parse_args()
    data = Path(os.environ.get("ROADPULSE_DATA", str(PROJECT / "data")))
    job = get_demo_job(data)
    folder = data / job["id"]
    video, csv_file, result = validate(job, folder)

    target = PROJECT / "docs" / "showcase"
    target.mkdir(parents=True, exist_ok=True)
    final_mp4 = target / "roadpulse-demo.mp4"
    temporary = target / "roadpulse-demo.partial.mp4"
    size = video.stat().st_size
    if size > LIMIT_BYTES and not args.compress:
        print(f"ANNOTATED_VIDEO_MIB={size / 1048576:.2f}")
        fatal("Video exceeds 40 MiB. Rerun with --compress to prepare a lightweight "
              "showcase copy (no AI rerun). Original video and results are untouched.")

    temporary.unlink(missing_ok=True)
    try:
        if size > LIMIT_BYTES:
            run_ffmpeg([
                "-threads", "1", "-i", str(video), "-an",
                "-vf", "scale=960:-2,fps=24", "-c:v", "libx264", "-threads", "1",
                "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(temporary),
            ])
            transform = "Full-length presentation copy resized to 960px wide and 24fps; one-thread H.264 encode."
        else:
            shutil.copy2(video, temporary)
            transform = "Byte-for-byte copy of the actual annotated MP4."
        if not temporary.exists() or not 1024 < temporary.stat().st_size <= LIMIT_BYTES:
            fatal("Presentation video still exceeds 40 MiB or is invalid; nothing published.")
        temporary.replace(final_mp4)
    finally:
        temporary.unlink(missing_ok=True)

    shutil.copy2(csv_file, target / "sample-events.csv")
    public = {
        "application": "RoadPulse AI",
        "footage": SOURCE_URL,
        "model": result["model"],
        "provider": result["provider"],
        "frames_processed": result["frames_processed"],
        "reported_frames": result.get("reported_frames"),
        "total_crossings": result["total"],
        "counts": result["counts"],
        "directions": result["directions"],
        "volume": result["volume"],
        "decode_warnings": result.get("decode_warnings", []),
        "presentation_note": transform,
    }
    (target / "sample-summary.json").write_text(
        json.dumps(public, indent=2) + "\n", encoding="utf-8"
    )

    poster = target / "poster.jpg"
    poster.unlink(missing_ok=True)
    try:
        run_ffmpeg([
            "-ss", "00:00:01", "-i", str(final_mp4),
            "-frames:v", "1", "-q:v", "3", str(poster),
        ])
    except (SystemExit, subprocess.TimeoutExpired) as exc:
        print("POSTER_WARNING=" + str(exc))
    provenance = (
        "# RoadPulse AI demonstration media\n\n"
        "- Footage: [Busy Urban Highway with Flowing Traffic](" + SOURCE_URL + ")\n"
        "- Creator: Faruk Yıldız (Pexels License).\n"
        "- Used as a computer-vision product demonstration, not standalone stock media.\n"
        "- Original footage was uploaded locally as demo.mp4 by the project owner.\n"
        "- Annotated video was produced by the local RoadPulse AI inference/tracking pipeline.\n"
        "- Analysis counts come from the corresponding completed job's CSV/JSON.\n"
        "- Presentation: " + transform + "\n"
        "- Presentation MP4 SHA256: " + digest(final_mp4) + "\n"
        "- Original exported MP4 SHA256: " + digest(video) + "\n"
        "- Do not imply Pexels or the creator endorses RoadPulse AI.\n"
        "- Check recognizable people/plates before publication.\n"
        "- Source identification is user-provided; independently check footage before publishing.\n"
    )
    (target / "MEDIA_PROVENANCE.md").write_text(provenance, encoding="utf-8")
    readme_path = PROJECT / "README.md"
    if poster.exists() and readme_path.is_file():
        readme = readme_path.read_text(encoding="utf-8")
        heading = "## Recorded traffic demonstration\n\n"
        preview = (
            "[![Watch the authentic RoadPulse AI traffic demonstration]"
            "(docs/showcase/poster.jpg)](docs/showcase/roadpulse-demo.mp4)\n\n"
        )
        if heading in readme and preview not in readme:
            readme_path.write_text(
                readme.replace(heading, heading + preview, 1), encoding="utf-8"
            )
    print("SHOWCASE_READY=YES")
    print("JOB_STATUS=" + job["status"])
    print("CROSSINGS=" + str(result["total"]))
    print(f"MP4_SIZE_MIB={final_mp4.stat().st_size / 1048576:.2f}")
    print("POSTER_READY=" + str(poster.exists()))
    print("OUTPUT=" + str(target))
    print("NEXT=Review video and provenance, then git add docs/showcase and push.")


if __name__ == "__main__":
    main()
