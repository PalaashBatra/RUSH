#!/usr/bin/env python3
"""
RUSH - one-command launcher.

    python3 run.py                 set up on first run, start API + UI, open the browser
    python3 run.py --no-browser    same, without opening a browser tab
    python3 run.py --reload        restart the API when files in app/ change

First run creates ./venv and installs requirements.txt. Later runs reuse it and
reinstall only when requirements.txt changes. Ctrl+C stops everything.
"""
import argparse
import hashlib
import http.server
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / "venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQUIREMENTS = ROOT / "requirements.txt"
STAMP = VENV / ".requirements.sha256"

# pydantic 2.9 / pydantic-core ship wheels for 3.9-3.13 only
MIN_PY, MAX_PY = (3, 9), (3, 13)


def fail(msg: str) -> None:
    print(f"\n  error: {msg}\n", file=sys.stderr)
    sys.exit(1)


def py_version(exe: str):
    try:
        out = subprocess.run([exe, "-c", "import sys; print(*sys.version_info[:2])"],
                             capture_output=True, text=True, timeout=10).stdout.split()
        return tuple(map(int, out)) if len(out) == 2 else None
    except (OSError, subprocess.SubprocessError):
        return None


def supported(v) -> bool:
    return v is not None and MIN_PY <= v <= MAX_PY


def find_python() -> str:
    """Pick an interpreter the pinned dependencies can install on."""
    candidates = [sys.executable] + [shutil.which(f"python3.{m}") for m in range(MAX_PY[1], MIN_PY[1] - 1, -1)]
    for exe in filter(None, candidates):
        if supported(py_version(exe)):
            return exe
    fail(f"needs Python {MIN_PY[0]}.{MIN_PY[1]}-{MAX_PY[0]}.{MAX_PY[1]} "
         f"(this is {sys.version_info.major}.{sys.version_info.minor}). Install e.g. python3.12 and rerun.")


def ensure_venv() -> None:
    if VENV_PY.exists() and not supported(py_version(str(VENV_PY))):
        fail(f"{VENV} was built with an unsupported Python. Delete the venv folder and rerun.")

    if not VENV_PY.exists():
        python = find_python()
        print(f"  creating venv with {python} ...")
        if subprocess.run([python, "-m", "venv", str(VENV)]).returncode != 0:
            shutil.rmtree(VENV, ignore_errors=True)
            fail("could not create the venv. On Debian/Ubuntu/Pop!_OS run:  sudo apt install python3-venv")

    want = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if not STAMP.exists() or STAMP.read_text().strip() != want:
        print("  installing dependencies (first run takes about a minute) ...")
        cmd = [str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(REQUIREMENTS)]
        if subprocess.run(cmd, cwd=ROOT).returncode != 0:
            fail("pip install failed. Check the output above, then rerun.")
        STAMP.write_text(want)


def port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if os.name != "nt":  # match uvicorn: a port in TIME_WAIT is still usable
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def next_free_port(host: str, port: int) -> int:
    for p in range(port, port + 50):
        if port_free(host, p):
            return p
    fail(f"no free port found between {port} and {port + 49}.")


def health(port: int):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.5) as r:
            data = json.load(r)
            return data if data.get("system", {}).get("routing_engine") else None
    except (OSError, ValueError):
        return None


# the only files the UI server will hand out, so nothing else in the project (like .env) is exposed
UI_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/SH.png": ("SH.png", "image/png"),
}


class UIHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        entry = UI_FILES.get(self.path.split("?", 1)[0])
        if not entry or not (ROOT / entry[0]).exists():
            self.send_error(404)
            return
        body = (ROOT / entry[0]).read_bytes()  # read per request so edits show up on refresh
        self.send_response(200)
        self.send_header("Content-Type", entry[1])
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def placeholder_key() -> bool:
    env = ROOT / ".env"
    if not env.exists():
        return False
    for line in env.read_text().splitlines():
        if line.strip().startswith("ANTHROPIC_API_KEY"):
            return "your_api_key_here" in line
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Start the RUSH API and UI.")
    ap.add_argument("--api-port", type=int, default=8000)
    ap.add_argument("--ui-port", type=int, default=5500)
    ap.add_argument("--host", default="127.0.0.1",
                    help="interface to bind (default 127.0.0.1; use 0.0.0.0 to expose on your network)")
    ap.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    ap.add_argument("--reload", action="store_true", help="restart the API when app/ changes")
    args = ap.parse_args()
    os.chdir(ROOT)
    sys.stdout.reconfigure(line_buffering=True)

    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print("\n  RUSH: Referral Upkeep System for Healthcare\n")
    try:
        serve(args)
    except KeyboardInterrupt:
        print("\n  stopping ...")
    finally:
        if RUNNING["ui"]:
            RUNNING["ui"].shutdown()
        proc = RUNNING["api"]
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


RUNNING = {"api": None, "ui": None}  # cleaned up by main() however we exit


def serve(args) -> None:
    ensure_venv()

    # API: reuse one that's already running, otherwise start our own
    api_port = args.api_port
    if health(api_port):
        print(f"  api already running on port {api_port}, reusing it")
    else:
        if not port_free(args.host, api_port):
            api_port = next_free_port(args.host, api_port + 1)
            print(f"  port {args.api_port} is busy, api will use {api_port}")
        cmd = [str(VENV_PY), "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", str(api_port),
               "--log-level", "warning"]
        if args.reload:
            cmd += ["--reload", "--reload-dir", "app"]
        api = RUNNING["api"] = subprocess.Popen(cmd, cwd=ROOT)
        deadline = time.time() + 30
        while not health(api_port):
            if api.poll() is not None:
                fail("the api exited during startup. See the error above.")
            if time.time() > deadline:
                fail("the api did not answer /health within 30s.")
            time.sleep(0.3)

    # UI
    ui_port = args.ui_port if port_free(args.host, args.ui_port) else next_free_port(args.host, args.ui_port + 1)
    RUNNING["ui"] = http.server.ThreadingHTTPServer((args.host, ui_port), UIHandler)
    threading.Thread(target=RUNNING["ui"].serve_forever, daemon=True).start()

    api_url = f"http://localhost:{api_port}"
    ai = (health(api_port) or {}).get("system", {}).get("ai_triage_available")
    if ai and placeholder_key():
        triage = "broken: .env still has the placeholder key, every call falls back to keywords"
    elif ai:
        triage = "api key found, claude will be tried (falls back to keywords if a call fails)"
    else:
        triage = "keyword fallback (add ANTHROPIC_API_KEY to .env for claude)"

    print(f"""
  ui      http://localhost:{ui_port}
  api     {api_url}
  docs    {api_url}/docs
  triage  {triage}

  ctrl+c to stop
""")
    if not args.no_browser:
        webbrowser.open(f"http://localhost:{ui_port}/?api={api_url}")

    api = RUNNING["api"]
    while api is None or api.poll() is None:
        time.sleep(0.5)
    fail("the api stopped unexpectedly. See the error above.")


if __name__ == "__main__":
    main()
