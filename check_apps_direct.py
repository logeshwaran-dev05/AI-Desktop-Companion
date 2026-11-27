import json
from api.app_catalogue import catalogue_service

# Retrieve all catalogued apps
apps = catalogue_service.get_all_apps()

# Build lookup maps (by name and id)
name_map = {app.get('app_name', '').lower(): app for app in apps}
id_map = {app.get('app_id', '').lower(): app for app in apps}

targets = [
    "Paint",
    "Paint 3D",
    "File Explorer",
    "Photos",
    "Camera",
    "Snipping Tool",
    "Clock",
    "Sticky Notes",
    "Voice Recorder",
    "Media Player",
    "Windows Security",
    "Microsoft Store",
    "Quick Assist",
    "Get Help",
    "Maps",
    "Feedback Hub",
    "Character Map",
    "Magnifier",
    "Remote Desktop",
    "Windows App",
]

for t in targets:
    key = t.lower()
    entry = name_map.get(key) or id_map.get(key)
    if not entry:
        # try fuzzy match on app_name containing the target
        matches = [a for a in apps if t.lower() in a.get('app_name', '').lower()]
        entry = matches[0] if matches else None
    if entry:
        launch_method = entry.get('launch_type') or entry.get('launch_method')
        app_id = entry.get('app_id') or entry.get('application_id')
        print(f"{t}: FOUND (id={app_id}, launch_method={launch_method})")
    else:
        print(f"{t}: NOT FOUND")
