# Engineering progress

- Created the isolated RoadPulse-AI project and Python 3.11 environment.
- Verified official YOLOX ONNX preprocessing/export contract and installed trackers.ByteTrackTracker API.
- CHECKPOINT_1_DETECTION=PASS: official model loaded; real traffic frame produced valid vehicle detections; model graph and SHA256 checked.
- Implemented streaming video processing, transactional SQLite job states, finite-line hysteresis, direction/class counts, annotation and H.264/CSV/JSON exports.
- CHECKPOINT_2_TRACKING=PASS: full 1,200-frame real video decoded and processed; tracking IDs present; exported video decoded for all 1,200 frames; CSV and JSON agree.
- Fixed overlapping cross-class proposals with class-agnostic NMS and added a regression test.
- Real spawned-worker API smoke passed on 180 contiguous real frames, including intermediate progress and running cancellation.
- Python suite: 24 tests passed; Ruff passed. Frontend type-check, lint and initial production build passed.
- Production HTTP dashboard, system/health proxy, real upload, preview and cancellation verified.
- Browser automation unavailable: inventory empty; creating an in-app browser returned unavailable. UI interaction/playback checks remain pending.
- Independent coarse visual review found seven car/SUV crossings. Broad-line inference produced nine events; annotated inspection identified two roadside equipment false positives. Lane-only benchmark completed: seven cars, 1,200 frames, matching the coarse count; this is not proof of precision/recall.
- Production npm audit: zero vulnerabilities. Full audit: five high entries from one unpatched braces development-tool advisory, disclosed in security notes.
- Cross-platform CI configured for Windows, Ubuntu and macOS; only Windows executed locally. No remote repository created or pushed.
- Installer replay was interrupted to stop laptop load. Existing package entrypoints remain present; four Windows npm command shims were restored without installation. Full transitive dependency validation remains pending.
- User reported repeated laptop shutdowns. Owned heavy processes and local services were stopped. No further model, video, install, build or server execution is authorized in this finishing pass.
- Added a conservative one-thread backend, cooperative frame pacing, cancellable rests, paced single-thread H.264 export, and limited future Next build concurrency/launcher Node heap.
- Latest low-impact changes receive syntax and four standard-library pacing tests only. Prior 24-test/model/build evidence applies to the earlier revision.
- CHECKPOINT_3_DASHBOARD=IMPLEMENTED_HTTP_VERIFIED_BROWSER_PENDING.
- CHECKPOINT_4_RELEASE=PARTIAL: browser/cross-platform verification, clean dependency replay and latest-source production rebuild remain pending. No remote publication performed.


## Small end-of-video discrepancy fix

A real uploaded job failed after 462 decoded frames against 465 container-reported frames. The former strict check discarded exports before encoding. Container counts alone do not establish whether the tail is corrupt or the metadata is approximate. The fix accepts a discrepancy only when it is at most three frames AND at most 1% of the reported count, exports the actual decoded frames and shows an explicit partial-analysis warning in the existing dashboard. JSON now records reported_frames and decode_warnings. Larger gaps and empty videos still fail. Progress completion means the available-frame analysis/export finished, not that all reported frames were recovered.

The old failed job retained only input.mp4 and preview.jpg; its results cannot be recovered without processing again. No input was modified, no job state was rewritten, and no automatic rerun/server restart was performed. Six standard-library regression cases and syntax validation are used for this change; full video validation is deferred to avoid laptop load.


## Standard/Fast revision (supersedes earlier low-impact pacing)

Added a Standard/Fast selector in dashboard source and validated/persisted mode through the API and worker. Standard uses one inference thread and one pending export frame; Fast uses up to two inference threads and two pending frames. Both process the same model and all readable frames. Removed the artificial 4x rests, 2-FPS export cap and intermediate video/two-pass export. Added a bounded ordered raw-frame pipe to one H.264 encoder, cached YOLOX grids, disabled ORT CPU spinning, stage-specific progress and actual encoded-frame counts. Final output frame count must match submitted frames. Analytic results are saved before finalizing MP4 and retained with CSV/JSON downloads if finalization fails.

Executed: 27 targeted tests (10 execution/export, 5 fixture worker, 6 API and 6 decode-gap), tiny real FFmpeg codec integration for both modes, TypeScript checking at 256-MiB heap, Ruff and Python syntax checks. Native inference was not run for the new modes. No measured speed multiplier or real-video equivalence is claimed. Full benchmark, browser and production rebuild remain pending due laptop load. The existing frontend production build predates the selector; a future rebuild is necessary to display it. Current design and official documentation references are in PERFORMANCE.md.

The launcher supports `scripts/start.py --mode fast` and `--mode standard`. Its default is passed through ROADPULSE_DEFAULT_MODE and applied when an older frontend omits mode in its start request; explicit API/dashboard mode selection overrides it. This allows both modes to be used with the retained frontend build, without rebuilding now. The new in-dashboard selector still requires a future frontend build. A regression test executed the older request shape against the Fast launcher default.

Final lightweight checks: Ruff passed; all 30 Python files parsed; TypeScript passed at a 256-MiB heap; ESLint passed for the changed dashboard page at a 256-MiB heap. No frontend production build, application server launch or full video benchmark was performed.
