import sys, os
sys.path.append(os.path.abspath('c:/Users/harir/OneDrive/Desktop/AI-Desktop-Companion'))
from api.orchestrator import TaskOrchestrator

orchestrator = TaskOrchestrator()
print('Orchestrator initialized')
print('Catalogue count:', len(orchestrator.get_catalogue()))
