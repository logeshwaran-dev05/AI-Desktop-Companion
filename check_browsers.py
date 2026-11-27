import sys
from api.app_catalogue import catalogue_service

apps = catalogue_service.get_all_apps()
targets = [
    'Google Chrome',
    'Microsoft Edge',
    'Mozilla Firefox',
    'Brave',
    'Opera',
    'Opera GX',
    'Vivaldi',
    'Tor Browser',
    'Chromium'
]
for t in targets:
    found = [a for a in apps if a.get('app_name') and t.lower() in a['app_name'].lower()]
    if found:
        a = found[0]
        launch = a.get('launch_type') or a.get('launch_method')
        app_id = a.get('app_id') or a.get('application_id')
        print(f"{t}: FOUND (id={app_id}, method={launch})")
    else:
        print(f"{t}: NOT FOUND")
