#!/usr/bin/env python3
"""Main entry point - launch backend, frontend, or both."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_backend(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn

    uvicorn.run("backend.main:app", host=host, port=port, reload=False)


def run_frontend(port: int = 8501):
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "frontend" / "app.py"),
            "--server.port",
            str(port),
            "--server.headless",
            "true",
        ],
        cwd=str(ROOT),
    )


def main():
    parser = argparse.ArgumentParser(description="Smart Traffic Monitoring System")
    parser.add_argument(
        "mode",
        choices=["backend", "frontend", "all"],
        default="backend",
        nargs="?",
        help="Run mode",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ui-port", type=int, default=8501)
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))

    if args.mode == "backend":
        run_backend(args.host, args.api_port)
    elif args.mode == "frontend":
        run_frontend(args.ui_port)
    else:
        import threading

        t = threading.Thread(target=run_backend, args=(args.host, args.api_port), daemon=True)
        t.start()
        run_frontend(args.ui_port)


if __name__ == "__main__":
    main()
