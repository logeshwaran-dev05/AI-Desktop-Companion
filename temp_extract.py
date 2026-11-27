import json, os, sys
raw_path = r"C:/Users/harir/.gemini/antigravity/brain/80359efe-d769-4d1e-8018-1f1315cc0b1a/.system_generated/steps/10/output.txt"
out_path = r"C:/Users/harir/.gemini/antigravity/brain/80359efe-d769-4d1e-8018-1f1315cc0b1a/application_catalogue.json"

with open(raw_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
json_str = ''
found = False
for line in lines:
    if not found and line.lstrip().startswith('['):
        found = True
    if found:
        json_str += line
apps = json.loads(json_str)
# write out pretty JSON
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(apps, f, indent=2)
print('TOTAL_APPS', len(apps))

