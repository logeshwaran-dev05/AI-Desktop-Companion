import subprocess, sys, time, os, signal
import httpx

def start_uvicorn():
    # Start uvicorn server as a subprocess
    cmd = [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "error"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc

def wait_for_server(url, timeout=10, interval=0.5):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(url, timeout=5.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False

def main():
    proc = start_uvicorn()
    try:
        # Wait until the health endpoint responds
        if not wait_for_server('http://127.0.0.1:8000/health'):
            print('Server did not become ready in time.')
            return
        # Health check
        health = httpx.get('http://127.0.0.1:8000/health')
        print('=== Health Check ===')
        print(f'Status code: {health.status_code}')
        print('Body:')
        print(health.text)
        # Docs page
        docs = httpx.get('http://127.0.0.1:8000/docs')
        print('=== Docs Page ===')
        print(f'Status code: {docs.status_code}')
    finally:
        # Terminate the server process
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        # Print any server output captured (optional)
        out, _ = proc.communicate(timeout=5)
        if out:
            print('--- Server output ---')
            print(out)

if __name__ == '__main__':
    main()
