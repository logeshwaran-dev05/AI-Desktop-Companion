import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app, orchestrator

class TestSequentialOrchestration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Create a task with two steps
        self.task_data = {
            "title": "Multi-step test",
            "description": "",
            "command": None,
            "auto_execute": True,
            "timeout_seconds": 5.0,
        }
        # Mock planner to return two steps
        self.plan_steps = [
            {"step_id": 1, "action": "copy_text", "target": "clipboard", "parameters": {"text": "hello"}},
            {"step_id": 2, "action": "paste_text", "target": "clipboard", "parameters": {}},
        ]
        # We'll patch the planner.process_command indirectly via orchestrator.create_task
        # Use patch on orchestrator.planner.process_command to return a dummy plan
        self.dummy_plan = MagicMock()
        self.dummy_plan.intent = "test"
        self.dummy_plan.message = ""
        self.dummy_plan.status = "plan_ready"
        self.dummy_plan.requires_clarification = False
        self.dummy_plan.clarification_question = None
        self.dummy_plan.steps = [
            type('Obj', (), {"step_id": 1, "action": "copy_text", "target": "clipboard", "parameters": {"text": "hello"}})(),
            type('Obj', (), {"step_id": 2, "action": "paste_text", "target": "clipboard", "parameters": {}})(),
        ]

    @patch('api.orchestrator.TaskOrchestrator.planner.process_command')
    @patch('api.orchestrator.TaskOrchestrator.adapter.execute_plan_step')
    def test_multi_step_success(self, mock_execute, mock_plan):
        # Mock planner
        mock_plan.return_value = self.dummy_plan
        # Mock execution results
        def exec_side_effect(step, task_id, authorization, timeout_seconds):
            result = MagicMock()
            result.action_id = f"act_{step.step_id}"
            result.status = "completed"
            result.duration_ms = 10
            result.completed_at = "2026-11-27T00:00:00Z"
            ver_details = {"output": step.parameters.get('text', '')}
            result.verification = MagicMock(verified=True, details=ver_details)
            result.verification.to_dict.return_value = {"verified": True, "details": ver_details}
            result.to_dict.return_value = {"status": "completed", "verification": {"verified": True, "details": ver_details}}
            result.audit = None
            return result
        mock_execute.side_effect = exec_side_effect
        # Submit task via API
        response = self.client.post('/tasks/submit', json={"title": "Test", "auto_execute": True, "command": "dummy"})
        self.assertIn(response.status_code, (200, 201))
        task = response.json()
        # Fetch task result
        task_id = task["task_id"]
        res = self.client.get(f'/tasks/{task_id}/result')
        self.assertEqual(res.status_code, 200)
        result = res.json()
        self.assertEqual(result["status"], "completed")
        # Ensure context passed: verification details from first step contain text
        self.assertIn("output", result["verification"].get("details", {}))

    @patch('api.main.get_browser_profiles')
    def test_browser_profiles_endpoint(self, mock_profiles):
        mock_profiles.return_value = [{"name": "Default", "path": "C:/Users/Test/AppData/Chrome/User Data/Default"}]
        response = self.client.get('/api/browser/profiles')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(data[0]["name"], "Default")

if __name__ == '__main__':
    unittest.main()
