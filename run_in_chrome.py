"""
Run Full AI Desktop Companion Project in Google Chrome.

This script:
1. Starts the FastAPI backend bridge (API + AI Planner + Windows Automation) on port 8000.
2. Starts the Vite Frontend dev server on port 5173 (or falls back to FastAPI static build).
3. Launches Google Chrome to http://localhost:5173 (or http://localhost:8000).
4. Handles clean shutdown on Ctrl+C.
"""

import os
import sys
import time
import socket
import subprocess
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DESKTOP_DIR = REPO_ROOT / "desktop"

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(port: int, timeout: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.3)
    return False


def get_chrome_path() -> str | None:
    for path in CHROME_PATHS:
        if os.path.exists(path):
            return path
    return None


def main():
    print("=" * 60)
    print("  AI Desktop Companion - Chrome Presentation Runner")
    print("  Author: Logeshwaran D (Windows Automation Lead)")
    print("=" * 60)

    # 1. Start FastAPI server
    print("\n[1/3] Starting Backend API Server (AI Engine + Windows Automation)...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.server:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(REPO_ROOT),
    )

    if not wait_for_port(8000, timeout=12.0):
        print("[-] Backend failed to start on port 8000.")
        backend_proc.terminate()
        return

    print("[+] Backend API online at http://127.0.0.1:8000")

    # 2. Start Vite Frontend Server
    print("\n[2/3] Starting Frontend Dev Server...")
    vite_proc = None
    target_url = "http://127.0.0.1:8000"  # fallback to built static app

    try:
        # Check if npm is available
        vite_proc = subprocess.Popen(
            ["npm.cmd", "run", "dev"],
            cwd=str(DESKTOP_DIR),
        )
        if wait_for_port(5173, timeout=8.0):
            print("[+] Vite dev server online at http://127.0.0.1:5173")
            target_url = "http://127.0.0.1:5173"
        else:
            print("[!] Vite server did not answer on 5173, falling back to static build on port 8000.")
    except Exception as e:
        print(f"[!] Could not start Vite dev server: {e}. Using FastAPI static build.")

    # 3. Launch Google Chrome
    print(f"\n[3/3] Launching Google Chrome to {target_url}...")
    chrome_path = get_chrome_path()
    if chrome_path:
        print(f"[+] Found Chrome: {chrome_path}")
        subprocess.Popen([chrome_path, target_url])
    else:
        print("[!] Chrome path not found in default locations. Opening default browser...")
        webbrowser.open(target_url)

    print("\n" + "=" * 60)
    print(f"  AI Desktop Companion is now RUNNING IN CHROME!")
    print(f"  URL: {target_url}")
    print("  Try typing commands in the composer, such as:")
    print("    - 'Open Notepad'")
    print("    - 'Launch Calculator'")
    print("    - 'Open Settings'")
    print("  Press Ctrl+C to terminate both servers when done.")
    print("=" * 60 + "\n")

    try:
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("[-] Backend process terminated unexpectedly.")
                break
    except KeyboardInterrupt:
        print("\n[*] Shutting down servers...")
    finally:
        if vite_proc:
            vite_proc.terminate()
        if backend_proc:
            backend_proc.terminate()
        print("[+] Servers stopped. Goodbye!")


if __name__ == "__main__":
    main()
