import json, sys, urllib.request, urllib.error
BASE='http://127.0.0.1:8000'
try:
    with urllib.request.urlopen(f'{BASE}/catalogue') as resp:
        apps=json.load(resp)
except Exception as e:
    print('Failed to fetch catalogue:', e)
    sys.exit(1)

name_map = {app.get('name','').lower(): app for app in apps}
id_map = {app.get('application_id','').lower(): app for app in apps}
# also include app_id if present
id_map.update({app.get('app_id','').lower(): app for app in apps})

targets = [
    "Paint","Paint 3D","File Explorer","Photos","Camera","Snipping Tool","Clock","Sticky Notes","Voice Recorder","Media Player","Windows Security","Microsoft Store","Quick Assist","Get Help","Maps","Feedback Hub","Character Map","Magnifier","Remote Desktop","Windows App"
]
for t in targets:
    key = t.lower()
    entry = name_map.get(key) or id_map.get(key)
    if not entry:
        # try fuzzy substring match
        matches = [app for app in apps if t.lower() in app.get('name','').lower()]
        if matches:
            entry = matches[0]
    if entry:
        launch_method = entry.get('launch_method') or entry.get('launch_type')
        app_id = entry.get('application_id') or entry.get('app_id')
        print(f"{t}: FOUND (id={app_id}, launch_method={launch_method})")
    else:
        print(f"{t}: NOT FOUND")
