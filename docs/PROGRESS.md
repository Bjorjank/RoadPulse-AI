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
