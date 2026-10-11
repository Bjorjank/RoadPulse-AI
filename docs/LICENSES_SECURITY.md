# Licenses, provenance and local security

## Source and model

RoadPulse original code: MIT (LICENSE). YOLOX: Apache-2.0, https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE. The official repository links the pretrained ONNX asset at https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx. No serialized PyTorch checkpoints are loaded. Model preparation checks the official release size, checks a published digest if present, validates the ONNX graph and executes a CPU inference, then records a local SHA256. This old release does not publish an independent checksum: local recording is integrity evidence, not an independent publisher signature. Later loads must match the recorded checksum.

The official Tiny profile is 416x416, BGR float32 in the 0-255 range, top-left letterboxed with 114 padding; raw outputs require stride-grid decode. No RGB conversion, division by 255 or ImageNet normalization is applied to this model. COCO category indices are car=2, motorcycle=3, bus=5, truck=7.

For reproducible custom export, use a separate export environment and the official YOLOX architecture and exporter: `python tools/export_onnx.py -n yolox-tiny -c yolox_tiny.pth --output-name yolox_tiny.onnx`. Obtain checkpoints only from the official release and inspect the matching official docs. Normal inference needs none of these training/export dependencies. A different export may include decoded outputs and requires validating its output contract before substituting it.

## Dependencies and media

- Roboflow trackers: Apache-2.0; https://github.com/roboflow/trackers.
- Supervision and ONNX Runtime: MIT. ONNX and OpenCV >=4.5: Apache-2.0. NumPy/SciPy: BSD-3-Clause.
- FastAPI, Pydantic, Uvicorn, Next.js, React, Tailwind and Recharts: MIT. SQLite: public domain.
- imageio-ffmpeg Python wrapper: BSD-2-Clause. Its bundled FFmpeg binary and libx264 have **GPL** terms; inspect the installed build's license before redistributing binaries. RoadPulse does not vendor FFmpeg in this repository. Users install it separately through the pinned dependency. Codec/patent obligations vary by use and jurisdiction; no universal commercial clearance is asserted.
- Optional media: **Temporary traffic signal at Colonel By Drive**, author **137a**, CC0 1.0. Source https://commons.wikimedia.org/wiki/File:Temporary_traffic_signal_at_Colonel_By_Drive.webm; license https://creativecommons.org/publicdomain/zero/1.0/. Local fixture resizes the complete video to 960px width, removes audio, and converts to H.264. Local manifest records source and transformed SHA256. Media/artifacts remain gitignored. License does not automatically waive privacy/publicity rights.
- COCO-trained weights may carry dataset-related conditions beyond code licensing. Individual dataset images have varied licenses. Do not claim blanket clearance for every model/data combination.

## Security scope

Single-user, loopback-only application. Random UUIDs isolate jobs; callers cannot request arbitrary filesystem paths. Artifact names use an exact allowlist and exports require completion. Uploads have simple MP4 filenames, a 1 GiB size limit, decoded-content validation and a 4K limit. Host and Origin validation reject unrelated websites; the frontend streams through a local same-origin proxy. No CORS wildcard, external API keys or external telemetry is added. Next telemetry is disabled in setup, launcher and CI.

This is not a multi-user service: anyone with access to the local process and a job ID can access that job. Do not expose it on a LAN or public interface without authentication, authorization, quotas, hardened media decoding and deployment review. Generated artifacts and input files persist locally for inspection. Cancelled or failed jobs remove partial exports but keep the uploaded source. Inspect storage before lengthy analyses; output and intermediate MP4s consume disk space.

Before publishing: inspect `git status --short` and `git ls-files`; verify models, private footage, artifacts, .env files and credentials remain excluded. Review dependencies with `python -m pip check` and `npm audit`; record unresolved findings accurately. Review public demo frames for identifiable faces/plates and obtain appropriate rights or redact them. Never publish a private source video merely because the app can process it.

## Dependency audit recorded during implementation

The current npm full audit reports five high-severity entries tracing to a single unpatched braces <=3.0.3 stack-exhaustion advisory in the ESLint development dependency chain. The advisory lists no patched version: https://github.com/advisories/GHSA-vfj7-8cjw-p6xm. The lint command operates on trusted repository paths, not uploaded input. Do not pass attacker-controlled glob patterns to these tools. An automatic forced downgrade is not applied; update the lint stack when a compatible fix is available. Inspect artifacts/npm-audit.json and artifacts/npm-audit-production.json for the actual recorded registry responses. This finding remains unresolved and must be disclosed in publication review.

Production-only npm audit executed with `npm audit --omit=dev` reported **zero** vulnerabilities. Full audit retains the development findings described above.
