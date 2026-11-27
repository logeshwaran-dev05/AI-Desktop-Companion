import json
from api.app_catalogue import catalogue_service

apps = catalogue_service.get_all_apps()
found = [a for a in apps if a.get('app_name') == 'Feedback Hub' or a.get('name') == 'Feedback Hub']
if not found:
    print('Feedback Hub NOT FOUND in catalogue')
else:
    for a in found:
        launch_method = a.get('launch_type') or a.get('launch_method')
        app_id = a.get('app_id') or a.get('application_id')
        print(f"Feedback Hub FOUND (id={app_id}, launch_method={launch_method})")
