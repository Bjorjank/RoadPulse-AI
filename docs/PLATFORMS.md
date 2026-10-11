# Platform and acceleration notes

Python 3.11 and CPU ONNX Runtime are the default across Windows x64, Ubuntu x64, macOS Intel and Apple Silicon where pinned wheels exist. Install Python 3.11 and Node 22+ using official installers. Use project-local environments. Windows uses Scripts/python.exe; Unix uses bin/python. No mandatory Docker, CUDA or system FFmpeg installation.

Only Windows has been executed in this development session. The GitHub Actions matrix covers Windows, Ubuntu and macOS configuration; those remote jobs are not claimed to have run. macos-latest architecture follows GitHub's runner image, so the matrix alone does not prove both Intel and Apple Silicon.

## Optional providers

Never install multiple ONNX Runtime distributions into one environment. Start with a separate project-local environment when experimenting; retain the default CPU environment for a working fallback.

- NVIDIA: replace onnxruntime with a compatible onnxruntime-gpu wheel and install the CUDA/cuDNN runtime versions required by that wheel. Consult https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html.
- Windows DirectML: replace onnxruntime with onnxruntime-directml. Consult https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html.
- macOS CoreML: use a runtime build exposing CoreMLExecutionProvider. Consult https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html. Availability alone is not proof of successful inference.

Detector preference is CUDA, CoreML, DirectML, CPU. It checks installed providers, constructs a session and executes an input before selecting it. Initialization failures are logged and CPU remains a fallback. The results report the active session provider; providers can internally assign unsupported graph nodes to CPU, so the label does not mean every operator executed on a GPU. No GPU acceleration is claimed from the Windows CPU measurements.

Execution mode Standard uses one ORT intra-op thread; Fast uses at most two (one on machines with fewer than four logical CPUs). Inter-op threads remain one with sequential graph execution; CPU thread spinning is disabled. Native math libraries and OpenCV decoding stay at one thread. One background job runs at a time. There are no artificial rests or input readrate limits in analysis/export. Both modes stream frames in order through a bounded FIFO queue directly into a single-thread H.264 encoder, with a one-frame queue in Standard and a two-frame queue in Fast. The final encoded frame count must match the number submitted, while metadata discrepancies are reported separately. Every readable source frame is analyzed. Next builds use one worker and the launcher limits the Node heap to 512 MiB. These settings bound application concurrency, not total OS CPU/RAM. See PERFORMANCE.md for references and validation limits. `ROADPULSE_DATA` selects a local runtime directory when running the API. Run scripts/doctor.py in the selected environment to inspect versions, available and selected providers, model checksum and initialization timing.

If dependency installation fails for an architecture, do not substitute a mock backend. Inspect wheel compatibility and test a compatible pin in a separate environment, then update the lockfile and record the platform's actual test results.
