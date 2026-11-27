import pathlib, sys
p = pathlib.Path(r'c:/Users/harir/OneDrive/Desktop/AI-Desktop-Companion/api/orchestrator.py')
lines = p.read_text(encoding='utf-8').splitlines()
for i in range(496,501):
    print(i+1, repr(lines[i]))

