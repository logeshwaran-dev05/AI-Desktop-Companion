'''Singleton module that creates and exposes the shared TaskOrchestrator instance.
This breaks the circular import between `api.main` and `api.catalogue_routes`.
Both modules import the orchestrator from here instead of each other.
''' 

from ai_engine.planner.task_planner import TaskPlanner
from api.orchestrator import TaskOrchestrator

# Global shared in‑memory task store (same dict used throughout the app)
_tasks: dict = {}

# Initialise planner and orchestrator once
planner = TaskPlanner()
orchestrator = TaskOrchestrator(planner=planner, tasks=_tasks)
