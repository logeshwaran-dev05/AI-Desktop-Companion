import json, sys
from api.app_catalogue import catalogue_service
apps = catalogue_service.get_all_apps()
json.dump(apps, sys.stdout, indent=2)
