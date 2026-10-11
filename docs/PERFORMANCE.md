# Standard and Fast execution

Documentation checked 2026-10-11. This revision replaces the earlier 4x-rest/2-FPS-export low-impact implementation.

## Same analytical work

Both modes use the identical verified YOLOX-Tiny ONNX model, FP32 input, 416x416 preprocessing, confidence/NMS thresholds, ByteTrack configuration, ordered decoded frames, original resolution annotation and counting geometry. There is no frame sampling, quantization, smaller model, lower input resolution or changed detection threshold. CPU thread scheduling can introduce small floating-point differences; no bit-exact real-video equivalence or accuracy guarantee is claimed without a real comparison run.

Standard is the safe default: one ORT intra-op thread and one pending export frame. Fast uses up to two intra-op threads (bounded by half the logical CPU count, at least one) and two pending export frames. A single background job remains the limit. Both disable ORT thread spinning, use sequential graph execution, one OpenCV decode thread, one encoder thread and one filter thread. Fast can increase CPU use; it is not an all-core mode.

## Single-pass architecture

Source decode -> YOLOX -> ByteTrack -> line counting -> annotation -> bounded FIFO -> FFmpeg raw BGR pipe -> H.264 MP4.

Inference/tracking stay sequential and ordered; the export thread overlaps encoding with the next frame's analysis. Queue capacity creates backpressure instead of dropping frames or growing memory without bounds. Partial pipe writes are handled explicitly. At most one/two frames wait in the queue, with additional in-flight frames and FFmpeg buffers. Encoder stdin receives original BGR dimensions and source FPS. Output uses libx264 ultrafast, CRF 18, yuv420p, even-dimension padding and faststart. Encoding is lossy, as before; the same export settings apply to both modes and analytical inference happens before encoding.

Removed: four-rests-per-unit-work delay, readrate throttling, intermediate MP4, second full-video decode and second encode. Cached YOLOX grids/strides avoid reconstructing fixed arrays per frame. These changes remove known work/delay; they do not establish a measured speed multiplier.

Progress publishes actual decoded/processed frames and FFmpeg's encoded frame count at most twice a second. It names INITIALIZING, ANALYZING and FINALIZING phases; 100% is only stored after successful encoder completion and atomic publication of annotated.mp4. Encoder output frame count must equal submitted frames. Counts/CSV plus analysis.json are checkpointed before finalization, with export_complete=false. An export failure preserves these analytics and offers CSV/analysis JSON downloads; incomplete MP4 remains unavailable.

A tiny tail discrepancy (at most 3 frames AND 1%) produces an explicit partial-analysis warning. Larger decode gaps still fail and preserve the streamed CSV. Metadata frame totals are not treated as a definitive decoded-frame count.

## Official documentation used

- [ONNX Runtime thread management](https://onnxruntime.ai/docs/performance/tune-performance/threading.html): intra-op thread counts, sequential execution and disabling spinning to reduce wasted CPU/power. The implementation deliberately caps threads rather than accepting the all-physical-core default.
- [FFmpeg pipe protocol](https://ffmpeg.org/ffmpeg-protocols.html#pipe): raw input through pipe:0. MP4 output is a regular seekable file, not an output pipe.
- [FFmpeg rawvideo demuxer](https://ffmpeg.org/ffmpeg-formats.html#rawvideo): explicit pixel format, dimensions and input frame rate.
- [FFmpeg libx264 options](https://ffmpeg.org/ffmpeg-codecs.html#libx264_002c-libx264rgb): preset and CRF quality control.
- [Python 3.11 queue](https://docs.python.org/3.11/library/queue.html): maxsize bounds, FIFO ordering and blocking insertion. No newer queue.shutdown API is used.

## Executed checks for this revision

- Ten standard-library profile/export tests: bounded thread settings, invalid modes, command construction, ordered lossless delivery of frame bytes despite partial pipe writes, queue-full cancellation, encoder failures and invalid raw-frame sizes.
- Five fixture worker integration tests: both modes preserve the same deterministic crossing/count/frame order; 462/465 warns and finishes; larger gaps fail; encoder finalization failure retains genuine fixture counts, CSV and JSON; mode contract validation.
- Six API tests with native model/video imports replaced by fixtures: selected mode persistence, Standard default, invalid mode rejection, advertised modes and failed-job artifact allowlist.
- Six end-of-video discrepancy regression tests.
- Actual FFmpeg integration: six synthetic 64x48 frames encoded and fully decoded for each mode. Both exported six frames with identical decoded hashes/order. Evidence: artifacts/mode-export-smoke.json. This is a codec software test, not traffic accuracy evidence or a benchmark.
- TypeScript --noEmit passed using a 256-MiB Node heap. Ruff and syntax checks are recorded in DELIVERY.md.

No full real-video analysis, full native-runtime test suite, browser test or production build has been run for this revision, to avoid stressing the laptop. Earlier measured FPS values are historical and do not describe these modes. The new selector is in frontend source; the retained production build predates it. API mode support becomes active after backend restart.

## Future real comparison on a stable machine

Run sequentially, with the same video, endpoints and machine load:

```text
python scripts/benchmark.py data/sample-traffic.mp4 --mode standard --line 0.1 0.5 0.45 0.5 --output artifacts/standard.json
python scripts/benchmark.py data/sample-traffic.mp4 --mode fast --line 0.1 0.5 0.45 0.5 --output artifacts/fast.json
```

Compare frames_processed, event CSVs, class/direction totals, provider and actual elapsed/processing_fps. Decode complete exports. Do not infer an accuracy score solely from matching totals or promise a speed multiplier from thread count. These commands are intentionally not executed now.

The launcher supports `scripts/start.py --mode fast` and `--mode standard`. Its default is passed through ROADPULSE_DEFAULT_MODE and applied when an older frontend omits mode in its start request; explicit API/dashboard mode selection overrides it. This allows both modes to be used with the retained frontend build, without rebuilding now. The new in-dashboard selector still requires a future frontend build. A regression test executed the older request shape against the Fast launcher default.

Final lightweight checks: Ruff passed; all 30 Python files parsed; TypeScript passed at a 256-MiB heap; ESLint passed for the changed dashboard page at a 256-MiB heap. No frontend production build, application server launch or full video benchmark was performed.
