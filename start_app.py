#!/usr/bin/env python3
"""Launch the local WhatsApp automation app with a single command."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"


def detect_python() -> str:
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def build_args(host: str, port: int, reload_mode: bool) -> list[str]:
    py = detect_python()
    cmd = [py, "-m", "uvicorn", "app.frontend:app", "--host", host, "--port", str(port)]
    if reload_mode:
        cmd.insert(2, "--reload")
    return cmd


def wait_for_server(host: str, port: int, timeout: float = 20.0) -> bool:
    import urllib.request

    url = f"http://{host}:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the WhatsApp task automation app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload mode")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open the browser")
    args = parser.parse_args()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    cmd = build_args(args.host, args.port, args.reload)
    print(f"Starting app: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env)

    try:
        ready = wait_for_server(args.host, args.port)
        if ready:
            print(f"App is running at http://{args.host}:{args.port}")
            if not args.no_browser:
                try:
                    webbrowser.open(f"http://{args.host}:{args.port}")
                except Exception:
                    pass
        else:
            print("Server may still be starting... check logs if needed.")

        signal.signal(signal.SIGINT, lambda signum, frame: None)
        while True:
            time.sleep(1)
            if proc.poll() is not None:
                return proc.returncode
    except KeyboardInterrupt:
        print("\nStopping app...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
