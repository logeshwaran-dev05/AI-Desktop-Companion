import json, sys
from api.app_catalogue import catalogue_service
apps = catalogue_service.get_all_apps()
# Find entries related to Network & Internet settings
matches = [a for a in apps if a.get('app_name') and ('Network' in a['app_name'] or 'Internet' in a['app_name'])]
if not matches:
    print('No Network/Internet settings entry found')
else:
    for a in matches:
        launch_method = a.get('launch_type') or a.get('launch_method')
        app_id = a.get('app_id') or a.get('application_id')
        print(f"{a.get('app_name')} -> id={app_id}, method={launch_method}")
