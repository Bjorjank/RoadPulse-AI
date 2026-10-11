# RoadPulse AI

Local traffic intelligence: MP4 -> YOLOX-Tiny ONNX -> Roboflow ByteTrack -> finite-line crossings -> dashboard and exports.

## Current local handoff

Implementation and authentic Windows validation are recorded in [DELIVERY.md](docs/DELIVERY.md). Services are stopped. Existing model, Python environment and an earlier production build are preserved. Do not repeat setup, model preparation, benchmarking or building on the stressed laptop now. The latest frontend source has small changes after that build; rebuilding it remains pending. The interrupted installer replay means dependency integrity is not fully revalidated.

When the laptop is ready, the existing production build can be opened manually from this directory:

```powershell
.\.venv\Scripts\python.exe scripts/start.py
```

Processing starts only after choosing Start analysis. The low-impact backend processes every frame with one-thread inference and deliberate rest periods; exports are also paced. Analysis will take longer. This profile was checked with lightweight pacing tests, but has deliberately not been benchmarked again. See [platform notes](docs/PLATFORMS.md).

## Requirements

Python **3.11** (64-bit), Node.js **22 LTS or newer**, npm, and enough disk space for uploaded and annotated video. CPU inference works without an NVIDIA GPU. Internet is required only for installation and optional asset preparation. Services bind to loopback.

## Install and run

Windows PowerShell, from this project directory:

```powershell
py -3.11 scripts/setup.py
.\.venv\Scripts\python.exe scripts/prepare_model.py
.\.venv\Scripts\python.exe scripts/doctor.py
$env:NEXT_TELEMETRY_DISABLED='1'
npm.cmd --prefix apps/web run build
.\.venv\Scripts\python.exe scripts/start.py
```

Linux / macOS:

```sh
python3.11 scripts/setup.py
.venv/bin/python scripts/prepare_model.py
.venv/bin/python scripts/doctor.py
NEXT_TELEMETRY_DISABLED=1 npm --prefix apps/web run build
.venv/bin/python scripts/start.py
```

Open **http://127.0.0.1:3000**. Upload a local MP4, click two line endpoints on the first-frame preview (or enter normalized coordinates), then choose **Start analysis**. The optional original-video player helps select a useful line. Every decoded frame is processed. Progress polls independently of inference. After completion, play or download the H.264 annotated MP4, events CSV, and summary JSON.

For development: `.venv` Python `scripts/start.py --dev`. API documentation: http://127.0.0.1:8000/docs. Ctrl+C stops the launcher. Jobs interrupted by a service restart are marked FAILED; upload again to restart. Data is kept locally under `data/` and is never committed.

## Verify

Use the environment's Python (`.\.venv\Scripts\python.exe` on Windows; `.venv/bin/python` on Unix):

```text
python -m pytest -q
python -m ruff check src scripts tests
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run build
python scripts/prepare_sample.py
python scripts/smoke.py data/sample-traffic.mp4
python scripts/benchmark.py data/sample-traffic.mp4 --line 0.1 0.5 0.9 0.5
```

The optional sample is real CC0 road footage, downloaded separately. `smoke.py` exercises the actual model, spawned worker, API, SQLite, cancellation, and exports on a short contiguous excerpt. `benchmark.py` processes the **entire** supplied MP4 and writes `artifacts/benchmark.json`; no fabricated timings or counts. Generated artifacts and media are ignored by Git. See [validation](docs/VALIDATION.md) for evidence and manual ground-truth instructions.

## Architecture

- `src/roadpulse/detection/`: official raw YOLOX output decoding, BGR top-left letterbox preprocessing, COCO mapping, score filtering, NMS, verified ONNX Runtime sessions.
- `src/roadpulse/analytics/`: bottom-center anchor movement across finite line segments, pixel hysteresis, direction state.
- `src/roadpulse/video/`: streaming decode, real ByteTrack tracking, annotations, event CSV, H.264 conversion, metrics.
- `src/roadpulse/jobs/`: typed contracts and transactional SQLite job states.
- `src/roadpulse/api.py`: FastAPI application, isolated upload directories, one spawned process worker, four active/queued jobs maximum.
- `apps/web/`: Next.js / TypeScript / Tailwind / Recharts dashboard; same-origin streaming API proxy.
- `scripts/`: reproducible local setup, model preparation, diagnostics, benchmark and launch commands.

No Redis, cloud inference, external telemetry, training, accounts, or API keys. No video frames accumulate in memory. Tracking history is bounded and pruned; inference latency samples are scalar values retained for exact median/p95 statistics.

## Counting semantics and limits

Normalized points are relative to the original frame, with coordinates in [0,1]. The exact-aspect preview maps click coordinates into that space. A -> B means crossing from the negative to positive signed side of the ordered endpoint line; B -> A is the reverse. Reversing endpoints reverses labels. These labels do not imply geographic travel direction.

A track can contribute at most **one event per direction** for the job. A genuine return journey can therefore contribute a second crossing. A four-pixel dead band rejects small fluctuations. Vehicles born on a line are not counted until movement establishes both sides. Only movement intersecting the finite segment qualifies. IDs are temporary within a job. Detection errors, class changes, occlusion, ID fragmentation, a moving camera, and low resolution can affect accuracy. This is not a vehicle re-identification or enforcement system.

Peak RAM is sampled worker RSS and excludes the separate FFmpeg encoder. Pipeline FPS includes initialization, decode, inference, tracking, counting, annotation, writing and final H.264 conversion. Model-only FPS measures ONNX `session.run`, excluding pre/postprocessing. Do not compare them as equivalent benchmarks. See [providers](docs/PLATFORMS.md) and [licenses/security](docs/LICENSES_SECURITY.md).

## Publication

A local Git repository is prepared only for this project. No remote repository is created or pushed automatically. Exclude `data/`, `models/`, `artifacts/`, environments, personal files, and credentials when publishing. No private footage belongs in a public repository. Consult the media attribution file and review any public demo for visible people or plates.
