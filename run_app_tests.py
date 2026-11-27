import json, os, sys, urllib.request, urllib.error, csv

BASE = 'http://127.0.0.1:8000'

def request(url, method='GET', data=None):
    req = urllib.request.Request(url, method=method)
    if data is not None:
        req.add_header('Content-Type', 'application/json')
        req.data = json.dumps(data).encode('utf-8')
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)

def main():
    # Health check with retries
    for attempt in range(5):
        try:
            health = request(f'{BASE}/health')
            print('Health check OK')
            break
        except Exception as e:
            print(f'Health check attempt {attempt+1} failed: {e}')
            if attempt < 4:
                import time
                time.sleep(2)
            else:
                sys.exit(1)

    # Get applications list with retries
    for attempt in range(5):
        try:
            apps = request(f'{BASE}/applications')
            break
        except Exception as e:
            print(f'Get apps attempt {attempt+1} failed: {e}')
            if attempt < 4:
                import time
                time.sleep(2)
            else:
                sys.exit(1)

    results = []
    for app in apps:
        app_id = app.get('id') or app.get('app_id')
        if not app_id:
            continue
        # Skip unsupported launch methods
        if app.get('launch_method') == 'unsupported':
            continue
        try:
            test_res = request(f'{BASE}/applications/{app_id}/test', method='POST')
            status = test_res.get('status')
            details = test_res.get('details')
        except Exception as e:
            status = 'ERROR'
            details = str(e)
        results.append({
            'application_id': app_id,
            'name': app.get('name'),
            'category': app.get('category'),
            'launch_method': app.get('launch_method'),
            'status': status,
            'details': details
        })

    # Write JSON report
    json_path = os.path.abspath('application_test_report.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print('JSON report written to', json_path)

    # Write CSV report
    csv_path = os.path.abspath('application_test_report.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['application_id', 'name', 'category', 'launch_method', 'status', 'details'])
        writer.writeheader()
        writer.writerows(results)
    print('CSV report written to', csv_path)

if __name__ == '__main__':
    main()
