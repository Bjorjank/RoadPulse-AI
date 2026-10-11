# Platform and acceleration notes

Python 3.11 and CPU ONNX Runtime are the default across Windows x64, Ubuntu x64, macOS Intel and Apple Silicon where pinned wheels exist. Install Python 3.11 and Node 22+ using official installers. Use project-local environments. Windows uses Scripts/python.exe; Unix uses bin/python. No mandatory Docker, CUDA or system FFmpeg installation.

Only Windows has been executed in this development session. The GitHub Actions matrix covers Windows, Ubuntu and macOS configuration; those remote jobs are not claimed to have run. macos-latest architecture follows GitHub's runner image, so the matrix alone does not prove both Intel and Apple Silicon.

## Optional providers

Never install multiple ONNX Runtime distributions into one environment. Start with a separate project-local environment when experimenting; retain the default CPU environment for a working fallback.

- NVIDIA: replace onnxruntime with a compatible onnxruntime-gpu wheel and install the CUDA/cuDNN runtime versions required by that wheel. Consult https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html.
- Windows DirectML: replace onnxruntime with onnxruntime-directml. Consult https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html.
- macOS CoreML: use a runtime build exposing CoreMLExecutionProvider. Consult https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html. Availability alone is not proof of successful inference.

Detector preference is CUDA, CoreML, DirectML, CPU. It checks installed providers, constructs a session and executes an input before selecting it. Initialization failures are logged and CPU remains a fallback. The results report the active session provider; providers can internally assign unsupported graph nodes to CPU, so the label does not mean every operator executed on a GPU. No GPU acceleration is claimed from the Windows CPU measurements.

ONNX Runtime intra-op and inter-op threads are fixed at one for the low-impact profile. OpenCV processing/decoding and native math libraries are also limited to one thread. After each processed frame, the worker rests for four times its active frame duration, checking cancellation every 250ms. This cooperative pacing targets about 20% active duty for the frame loop; it is not an OS CPU or total-memory quota. Every frame is still processed. H.264 export uses one thread, ultrafast encoding and input pacing of at most two video frames per wall-clock second. Next builds use one worker and the launcher limits the Node heap to 512 MiB. These settings favor a quieter laptop over throughput; they cannot guarantee prevention of hardware shutdowns. `ROADPULSE_DATA` selects a local runtime directory when running the API. Run scripts/doctor.py in the selected environment to inspect versions, available and selected providers, model checksum and initialization timing.

If dependency installation fails for an architecture, do not substitute a mock backend. Inspect wheel compatibility and test a compatible pin in a separate environment, then update the lockfile and record the platform's actual test results.
