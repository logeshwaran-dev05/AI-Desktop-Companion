import sys, os
sys.path.append(os.path.abspath('c:/Users/harir/OneDrive/Desktop/AI-Desktop-Companion'))
try:
    from api.orchestrator import TaskOrchestrator
    print('Import succeeded')
except Exception as e:
    print('Import error:', e)
