warning: in the working copy of 'api/orchestrator.py', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/api/orchestrator.py b/api/orchestrator.py[m
[1mindex dd0bd23..26f2581 100644[m
[1m--- a/api/orchestrator.py[m
[1m+++ b/api/orchestrator.py[m
[36m@@ -346,7 +346,7 @@[m [mclass ApplicationResolver:[m
                 if app["app_id"] == aliased_id:[m
                     return app[m
 [m
[31m-        # 3. Windows Application Catalogue (dynamic — covers Settings pages, built-ins, third-party)[m
[32m+[m[32m        # 3. Windows Application Catalogue (dynamic — covers Settings pages, built-ins, third‑party)[m
         catalogue_entry = _windows_catalogue.resolve_phrase(target)[m
         if catalogue_entry:[m
             return {[m
[36m@@ -439,7 +439,7 @@[m [mclass PermissionEvaluator:[m
                 reason=f"Application '{matched_app}' is installed in catalogue but requires explicit user approval before launching.",[m
             )[m
 [m
[31m-        # 3. Not in allowlist and not in catalogue -> Denied[m
[32m+[m[32m        # 3. Not in allowlist and not in catalogue → Denied[m
         return AuthorizationDecision([m
             decision_id=decision_id,[m
             permission_status="denied",[m
[36m@@ -465,7 +465,6 @@[m [mclass TaskOrchestrator:[m
         tasks: Optional[Dict[str, Dict[str, Any]]] = None,[m
     ):[m
         # Initialize components[m
[31m-[m
         self.adapter = adapter or WindowsAutomationAdapter()[m
         # Initialize SQLite task repository[m
         self.repo = TaskRepository()[m
[36m@@ -477,7 +476,7 @@[m [mclass TaskOrchestrator:[m
         self.permission_evaluator = PermissionEvaluator()[m
         self.resolver = ApplicationResolver()[m
         self.state_machine = TaskStateMachine()[m
[31m-        # In‑memory register mapping idempotency_key -> task_id[m
[32m+[m[32m        # In‑memory register mapping idempotency_key → task_id[m
         self._idempotency_registry: Dict[str, str] = {}[m
 [m
     def _persist_task(self, task_id: str) -> None:[m
[36m@@ -486,17 +485,6 @@[m [mclass TaskOrchestrator:[m
         if task:[m
             self.repo.update_task(task_id, task)[m
 [m
[31m-[m
[31m-        self.adapter = adapter or WindowsAutomationAdapter()[m
[31m-        self.repo = TaskRepository()[m
[31m-        # Load persisted tasks into in‑memory dict for fast access[m
[31m-        self.tasks: Dict[str, Dict[str, Any]] = tasks if tasks is not None else {t["task_id"]: t for t in self.repo.list_tasks()}[m
[31m-        self.permission_evaluator = PermissionEvaluator()[m
[31m-        self.resolver = ApplicationResolver()[m
[31m-        self.state_machine = TaskStateMachine()[m
[31m-        # In-memory register mapping idempotency_key -> task_id[m
[31m-        self._idempotency_registry: Dict[str, str] = {}[m
[31m-[m
     # -----------------------------------------------------------------------[m
     # Application Catalogue[m
     # -----------------------------------------------------------------------[m
[36m@@ -572,18 +560,17 @@[m [mclass TaskOrchestrator:[m
     ) -> Dict[str, Any]:[m
         """[m
         Common execution pipeline for all user requests (voice and text).[m
[31m-        [m
[32m+[m
         Flow:[m
[31m-        User Input -> Voice/Text Processing -> AI Intent -> Application Matching ->[m
[31m-        Windows Automation -> Verification -> Task Status (launched / failed)[m
[32m+[m[32m        User Input → Voice/Text Processing → AI Intent → Application Matching →[m
[32m+[m[32m        Windows Automation → Verification → Task Status (launched / failed)[m
         """[m
         # Step 1: Idempotency Gate[m
[31m-        if idempotency_key:[m
[31m-            if idempotency_key in self._idempotency_registry:[m
[31m-                existing_id = self._idempotency_registry[idempotency_key][m
[31m-                raise DuplicateRequestError([m
[31m-                    f"Duplicate request detected for idempotency key '{idempotency_key}'. Task ID: '{existing_id}'."[m
[31m-                )[m
[32m+[m[32m        if idempotency_key and idempotency_key in self._idempotency_registry:[m
[32m+[m[32m            existing_id = self._idempotency_registry[idempotency_key][m
[32m+[m[32m            raise DuplicateRequestError([m
[32m+[m[32m                f"Duplicate request detected for idempotency key '{idempotency_key}'. Task ID: '{existing_id}'."[m
[32m+[m[32m            )[m
 [m
         # Step 2: Task Record Initialization[m
         task_id = task_id or f"task_{uuid4()}"[m
[36m@@ -652,7 +639,7 @@[m [mclass TaskOrchestrator:[m
         plan_response = self.planner.process_command(CommandRequest(text=command, input_type=input_type))[m
         task["intent"] = plan_response.intent[m
 [m
[31m-        # Step 4.1: Check for Ambiguous Command or Clarification Required[m
[32m+[m[32m        # Step 4.1: Ambiguity / Clarification[m
         clean_cmd = (command or "").strip().lower()[m
         is_launch_command = any([m
             clean_cmd.startswith(prefix)[m
[36m@@ -677,22 +664,19 @@[m [mclass TaskOrchestrator:[m
             task["completed_at"] = current_iso_timestamp()[m
             return task[m
 [m
[31m-        # Step 4.2: Handle Unsupported or Missing Steps with Alternative Phrase / Category Recovery[m
[32m+[m[32m        # Step 4.2: Unsupported / Missing Steps – try fallback resolution[m
         if plan_response.status == "unsupported" or not plan_response.steps:[m
             if is_launch_command:[m
[31m-                # Try category / alternative phrase resolution (e.g. "Can you open my browser?")[m
                 resolved_app = self.resolver.resolve(target_candidate) or self.resolver.resolve(clean_cmd)[m
                 if resolved_app:[m
                     task["intent"] = "open_application"[m
[31m-                    task["steps"] = [[m
[31m-                        {[m
[31m-                            "step_id": 1,[m
[31m-                            "action": "open_application",[m
[31m-                            "target": resolved_app["app_name"],[m
[31m-                            "depends_on": [],[m
[31m-                            "expected_outcome": f"{resolved_app['app_name']} should open successfully.",[m
[31m-                        }[m
[31m-                    ][m
[32m+[m[32m                    task["steps"] = [{[m
[32m+[m[32m                        "step_id": 1,[m
[32m+[m[32m                        "action": "open_application",[m
[32m+[m[32m                        "target": resolved_app["app_name"],[m
[32m+[m[32m                        "depends_on": [],[m
[32m+[m[32m                        "expected_outcome": f"{resolved_app['app_name']} should open successfully.",[m
[32m+[m[32m                    }][m
                 else:[m
                     self.state_machine.transition(task, "failed", f"Unknown application: '{target_candidate}' is not recognized.")[m
                     task["error_code"] = "ERR_UNKNOWN_APPLICATION"[m
[36m@@ -788,10 +772,15 @@[m [mclass TaskOrchestrator:[m
             task, "launching", f"Dispatching '{action_name}' on '{canonical_target}' to Windows Automation."[m
         )[m
 [m
[31m-                                # Build the PlanStep with merged parameters[m
[31m-[m
[31m-[m
[31m-[m
[32m+[m[32m        # Build the PlanStep with merged parameters (no extra params at this point)[m
[32m+[m[32m        plan_step = PlanStep([m
[32m+[m[32m            step_id=step_data.get("step_id", 1),[m
[32m+[m[32m            action=action_name,[m
[32m+[m[32m            target=canonical_target,[m
[32m+[m[32m            depends_on=step_data.get("depends_on", []),[m
[32m+[m[32m            expected_outcome=step_data.get("expected_outcome", ""),[m
[32m+[m[32m            parameters={},[m
[32m+[m[32m        )[m
 [m
         try:[m
             exec_result: ExecutionResult = self.adapter.execute_plan_step([m
[36m@@ -808,6 +797,7 @@