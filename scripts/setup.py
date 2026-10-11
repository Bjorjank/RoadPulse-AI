"""Cross-platform project-local installation. Run using Python 3.11."""

import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.version_info[:2] != (3, 11):
        raise SystemExit(
            "Use Python 3.11: py -3.11 scripts/setup.py (Windows), python3.11 scripts/setup.py (Unix)"
        )
    node, npm = shutil.which("node"), shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not node or not npm:
        raise SystemExit("Install Node.js 22 LTS or newer with npm, then rerun setup")
    env = ROOT / ".venv"
    if not env.exists():
        venv.EnvBuilder(with_pip=True).create(env)
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    commands = [
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        [str(python), "-m", "pip", "install", "-r", "requirements.lock"],
        [str(python), "-m", "pip", "install", "--no-deps", "-e", ".[dev]"],
        [npm, "ci"],
    ]
    settings = {**os.environ, "NEXT_TELEMETRY_DISABLED": "1"}
    for command in commands:
        subprocess.run(
            command, cwd=ROOT / "apps/web" if command[0] == npm else ROOT, env=settings, check=True
        )
    print(
        "Setup complete. Next: .venv Python -> scripts/prepare_model.py, scripts/doctor.py, scripts/start.py"
    )


if __name__ == "__main__":
    main()
