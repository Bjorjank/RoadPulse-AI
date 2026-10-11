# RoadPulse AI V1 local delivery

Updated 2026-10-11. Project: C:/laragon/www/RoadPulse-AI. All computation and media storage are local. No remote repository was created or pushed.

## Delivered implementation

- Official YOLOX-Tiny ONNX inference with verified hash, correct raw-grid decoding, letterboxing, class-agnostic NMS and four vehicle categories.
- Roboflow trackers ByteTrack, temporary IDs, optional trails, finite normalized line, hysteresis and once-per-track/per-direction counting.
- Full sequential video processing, SQLite state/progress, one spawned worker, cancellation, isolated uploads, annotated H.264 MP4, CSV and JSON.
- Next.js dashboard with upload/preview/line editor, results, actual progress/provider, charts, download/playback controls and streaming same-origin API proxy.
- Pinned environments, model/sample preparation, local launcher, tests, cross-platform CI configuration, license/security and validation notes.

## Executed evidence before the low-impact revision

CHECKPOINT_1_DETECTION=PASS. Official ONNX graph/checksum validation and real-frame detection executed. Model source: https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx

Model size: 20,219,662 bytes. SHA256: `427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7`. This older release has no upstream published digest; the recorded local hash is not an independent publisher signature. Model preparation verifies the pinned hash, HTTPS release metadata size and ONNX graph.

CHECKPOINT_2_TRACKING=PASS. Real CC0 sample by 137a: https://commons.wikimedia.org/wiki/File:Temporary_traffic_signal_at_Colonel_By_Drive.webm . Full-duration 960x540 MP4, 59.940063 FPS, 1,200 frames. Both complete runs produced 4,928 tracked observations on CPUExecutionProvider.

| Line endpoints | Counts | Pipeline FPS | Elapsed seconds | Mean inference ms | Sampled worker peak RSS |
| --- | --- | --- | --- | --- | --- |
| (0.1,0.5) to (0.9,0.5) | 7 cars + 2 false-positive trucks | 4.6112 | 260.236 | 162.33 | 224,382,976 bytes |
| (0.1,0.5) to (0.45,0.5) | 7 cars, all A_TO_B | 3.6199 | 331.499 | 204.59 | 223,789,056 bytes |

Broad-line output was fully decoded for all 1,200 frames and CSV/JSON agreement checked. Lane CSV/JSON agreement was separately checked using the standard library in the final lightweight pass. The lane export was produced successfully, but a separate complete decode of that export was not repeated. These timings predate low-impact pacing and were measured during development activity, not a controlled idle-machine performance study. RSS excludes the separate encoder and frontend.

Independent original-frame contact sheets at 0.5-second intervals showed seven car/SUV crossings; approximate intervals are in reference-ground-truth.csv. Count agreement is provisional and does not establish precision, recall or frame-accurate timing. Wide-line false trucks were roadside equipment during camera movement. The line adjustment excludes that equipment without altering the model results.

Evidence retained locally (gitignored): artifacts/detection-smoke.json, benchmark.json, benchmark-wide-line.json, benchmark-lane.json, export-verification.json, api-smoke.json and their generated media/job folders.

The real 180-frame spawned-worker API smoke passed: 760 tracked observations, one crossing, intermediate progress, actual inference, readable MP4, consistent CSV/JSON/API results, artifact allowlist and running cancellation. This used TestClient plus the real spawned processing worker. The optional --url production-HTTP smoke mode was added later and has not been executed.

Python: 24 tests passed and Ruff passed. Frontend lint, TypeScript checking and initial production build passed. Production HTTP page, proxy health/system, real upload, JPEG preview and cancellation were verified. Small frontend job-restore/provider changes were added after that build and have not been rebuilt.

## Laptop resource constraint and final checks

After the user reported repeated laptop shutdowns, owned heavy processes and services were stopped. No new installation, model run, video analysis, production build or server launch was performed in the final pass.

Low-impact source defaults now use one-thread ORT/native math/OpenCV decoding, four units of rest per unit of active frame work, and cancellation checks during rest. H.264 export has single-thread decode/encode, ultrafast preset and input pacing of at most two frames per second. All source frames remain processed. Next build concurrency is limited to one and the launcher limits Node heap to 512 MiB. These are conservative application settings, not a hard OS-wide CPU/RAM limit or a guarantee against shutdowns. Hardware/thermal causes were not diagnosed.

Executed after these changes: four standard-library pacing tests passed (rest ratio, bounded sleep intervals, immediate cancellation, cancellation during rest, zero-work behavior covered across four tests); all 24 Python source/test files parsed; node --check accepted next.config.mjs; lane CSV/JSON agreed on seven cars. No native model/video runtime was loaded for these checks. Real inference and encoding with the new limits remain unverified to avoid stressing the laptop.

The replay of npm ci was interrupted. Installed package entrypoints remain present and four missing Windows command shims were restored with file writes. This does not prove complete transitive dependency integrity. The existing production build is preserved; it represents the earlier frontend revision.

## Remaining release verification

CHECKPOINT_3_DASHBOARD=IMPLEMENTED_HTTP_VERIFIED_BROWSER_PENDING. Browser inventory was empty and opening an in-app browser returned unavailable. Interactive line placement, chart interaction, responsive layouts and browser playback therefore have no claimed browser PASS.

CHECKPOINT_4_RELEASE=PARTIAL. Latest-source production rebuild, clean dependency replay, low-impact real-video rerun, browser checks and remote cross-platform CI remain pending. Windows is the only executed platform. Linux/macOS use the same code and configured CI matrix, but were not executed here. Variable-frame-rate timing is not validated; event timestamps currently use frame index divided by reported FPS.

Production npm audit reported zero vulnerabilities before the interrupted replay. Full audit reported five high dependency entries from the unpatched development-tool braces advisory GHSA-vfj7-8cjw-p6xm: https://github.com/advisories/GHSA-vfj7-8cjw-p6xm . See LICENSES_SECURITY.md. No claim of zero development advisories is made.

## Local operation when the laptop is ready

Do not repeat setup, build or benchmarks now. From the project directory, the preserved build can be started manually:

```powershell
.\.venv\Scripts\python.exe scripts/start.py
```

Open http://127.0.0.1:3000. Nothing is analyzed until Start analysis is selected. Ctrl+C stops the launcher. Startup itself has not been repeated after the final limits. The install/rebuild commands in README are for deliberate future verification on a stable machine, not instructions to run them immediately.

## Reproducibility and publication

Validated environment: Python 3.11.2; Node 24.15.0; npm 11.12.1; ONNX Runtime 1.31.0; OpenCV 5.0.0.93; NumPy 2.4.6; trackers 2.6.1; supervision 0.30.9; FastAPI 0.143.0; Pydantic 2.14.0; Next 16.4.0; React 19.3.0. Exact dependency pins are in requirements.lock and apps/web/package-lock.json.

Source is prepared in a local Git repository. Models, footage, exports, environments, node_modules, caches and credentials are excluded. No API keys or remote inference are required. Remote publication requires explicit user authorization. The optional sample is CC0; YOLOX is Apache-2.0; bundled FFmpeg/libx264 licensing and redistribution considerations are documented separately.
