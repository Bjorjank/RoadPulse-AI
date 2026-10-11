"""Execution settings only; model, thresholds and frames are identical."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionProfile:
    name: str
    inference_threads: int
    pending_frames: int


def execution_profile(name="standard", *, cpu_count=None):
    if name not in {"standard", "fast"}:
        raise ValueError("Choose standard or fast")
    logical = max(1, cpu_count if cpu_count is not None else (os.cpu_count() or 1))
    # Keep Fast bounded even on large machines; never choose all cores implicitly.
    threads = min(2, max(1, logical // 2)) if name == "fast" else 1
    return ExecutionProfile(name, threads, 2 if name == "fast" else 1)
