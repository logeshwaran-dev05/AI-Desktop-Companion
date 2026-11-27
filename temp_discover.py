import json, sys
sys.path.append('c:/Users/harir/OneDrive/Desktop/AI-Desktop-Companion')
import api.app_catalogue as ac
print(json.dumps(ac.get_windows_catalogue(), indent=2))

