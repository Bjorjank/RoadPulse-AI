import argparse
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true", help="Use Next development mode instead of production")
    parser.add_argument(
        "--mode",
        choices=["standard", "fast"],
        default="standard",
        help="Default execution mode, including for older frontend builds",
    )
    args = parser.parse_args()
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    node = shutil.which("node")
    if not python.exists() or not node:
        raise SystemExit("Run scripts/setup.py first")
    if not args.dev and not (ROOT / "apps/web/.next/BUILD_ID").exists():
        raise SystemExit("Build frontend first: npm --prefix apps/web run build (or use --dev)")
    for port in (8000, 3000):
        import socket

        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(f"Port {port} is already in use; close that service or reuse it")
    environment = {**os.environ, "NEXT_TELEMETRY_DISABLED": "1", "PYTHONUNBUFFERED": "1"}
    environment.update(
        {
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "UV_THREADPOOL_SIZE": "1",
            "NODE_OPTIONS": "--max-old-space-size=512",
            "ROADPULSE_DEFAULT_MODE": args.mode,
        }
    )
    children = []
    try:
        children.append(
            subprocess.Popen(
                [str(python), "-m", "uvicorn", "roadpulse.api:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=ROOT,
                env=environment,
            )
        )
        children.append(
            subprocess.Popen(
                [
                    node,
                    str(ROOT / "apps/web/node_modules/next/dist/bin/next"),
                    "dev" if args.dev else "start",
                    "--hostname",
                    "127.0.0.1",
                    "--port",
                    "3000",
                ],
                cwd=ROOT / "apps/web",
                env=environment,
            )
        )
        for _ in range(120):
            if any(p.poll() is not None for p in children):
                raise RuntimeError("A service exited during startup; inspect terminal output")
            try:
                with urllib.request.urlopen("http://127.0.0.1:3000/api/health", timeout=2) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Services did not become ready")
        print(
            f"RoadPulse AI ready: http://127.0.0.1:3000 | default mode: {args.mode.upper()} | Ctrl+C stops both services",
            flush=True,
        )
        while all(p.poll() is None for p in children):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in children:
            if p.poll() is None:
                p.terminate()
        for p in children:
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


if __name__ == "__main__":
    main()
