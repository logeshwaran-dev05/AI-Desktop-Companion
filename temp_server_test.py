import threading, time, sys
import uvicorn
import httpx

def run_uvicorn():
    # Run uvicorn server; set reload=False for simplicity
    uvicorn.run('api.main:app', host='127.0.0.1', port=8000, log_level='error')

# Start server in a daemon thread so it exits when main thread ends
server_thread = threading.Thread(target=run_uvicorn, daemon=True)
server_thread.start()
# Give server time to start up
time.sleep(3)

def print_response(label, resp):
    print(f"=== {label} ===")
    print(f"Status code: {resp.status_code}")
    # Print first 200 chars of body for brevity
    body = resp.text
    if len(body) > 200:
        body = body[:200] + "..."
    print("Body:")
    print(body)
    print("---")

# Health check
try:
    health_resp = httpx.get('http://127.0.0.1:8000/health')
    print_response('Health Check', health_resp)
except Exception as e:
    print('Health check error:', e)

# Docs page
try:
    docs_resp = httpx.get('http://127.0.0.1:8000/docs')
    print_response('Docs Page', docs_resp)
except Exception as e:
    print('Docs fetch error:', e)

# Exit (daemon thread will be terminated)
sys.exit(0)
