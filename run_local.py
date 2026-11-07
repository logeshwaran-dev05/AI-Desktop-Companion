"""
Interactive Local Runner for AI Desktop Companion — Windows Automation.

Allows live interactive testing of:
1. Installed Application Discovery (ApplicationDiscoverer).
2. Application Catalogue and target resolution (ApplicationCatalogue).
3. Natural language command understanding (Booviha's ai_engine).
4. Permission & policy validation (WindowsActionPolicy).
5. Controlled Windows launch (subprocess, shell=False).
6. Win32 window readiness verification (EnumWindows).
7. Safe cancellation and process cleanup.
"""

import sys
import time
import uuid

# Ensure root workspace is in sys.path
sys.path.insert(0, ".")

from ai_engine.schemas.command_schema import CommandRequest
from ai_engine.planner.task_planner import TaskPlanner
from windows_automation.adapter import WindowsAutomationAdapter
from windows_automation.schemas import AuthorizationDecision


def print_banner():
    print("=" * 72)
    print("  JM VERTEX TECHNOLOGIES — AI DESKTOP COMPANION (LOCAL RUNNER)")
    print("  Module: Windows Automation — Discovery & Controlled Safe Launch")
    print("  Created by: Logeshwaran D")
    print("=" * 72)
    print("Commands:")
    print("  - Type 'scan' or 'apps' to discover all installed applications.")
    print("  - Type an app name or action (e.g. 'Open Notepad', 'Open Chrome', 'calc').")
    print("  - Type 'test' to run all 25 unit and live integration tests.")
    print("  - Type 'exit' or 'quit' to exit.")
    print("-" * 72)


def run_interactive():
    adapter = WindowsAutomationAdapter()
    planner = TaskPlanner()

    print_banner()
    print("[*] Performing initial Windows application discovery...")
    discovery = adapter.refresh_catalogue()
    print(f"[*] Discovered {discovery.total_discovered} registered application(s) across {len(discovery.sources_scanned)} source(s).\n")

    while True:
        try:
            user_input = input("Enter Command > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not user_input:
            continue

        cmd_lower = user_input.lower()

        if cmd_lower in ("exit", "quit", "q"):
            print("Goodbye!")
            break

        if cmd_lower in ("scan", "apps", "list"):
            apps = adapter.get_catalogue().get_all()
            print(f"\n--- Discovered Applications Catalogue ({len(apps)} entries) ---")
            for idx, a in enumerate(apps, 1):
                source_tag = f"[{a.source}]"
                print(f" {idx:2d}. {a.display_name:<30} {source_tag:<20} ID: {a.app_id}")
            print("-" * 65)
            continue

        if cmd_lower == "test":
            print("\n[Running Full Test Suite...]")
            import unittest
            suite = unittest.defaultTestLoader.discover("windows_automation/tests")
            runner = unittest.TextTestRunner(verbosity=2)
            runner.run(suite)
            continue

        # Step 1: AI Planner parsing (if applicable)
        plan_step = None
        target_name = user_input

        if cmd_lower.startswith(("open ", "launch ", "start ")):
            req = CommandRequest(text=user_input)
            plan = planner.process_command(req)
            if plan.steps:
                plan_step = plan.steps[0]
                target_name = plan_step.target

        # Step 2: Resolve target against Catalogue
        print(f"\n[1] Resolving target: '{target_name}'...")
        resolution = adapter.resolve_application(target_name)

        if resolution.status == "not_found":
            print(f"    [!] Not Found: {resolution.reason}")
            continue
        elif resolution.status == "ambiguous":
            print(f"    [!] Ambiguous: {resolution.reason}")
            print("    Please specify which one you meant:")
            for c in resolution.candidates:
                print(f"      - {c.display_name} (ID: {c.app_id})")
            continue
        elif resolution.status == "unsupported":
            print(f"    [!] Unsupported: {resolution.reason}")
            continue

        rec = resolution.matched_record
        print(f"    [+] Resolved to: '{rec.display_name}'")
        print(f"        * App ID: {rec.app_id}")
        print(f"        * Executable: {rec.executable_path}")
        print(f"        * Source: {rec.source}")

        # Step 3: Authorization Gate
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        auth = AuthorizationDecision(
            decision_id=f"dec_{uuid.uuid4().hex[:8]}",
            permission_status="granted",
            requires_user_approval=False,
            approval_reference="user_cli_session",
            reason=f"Application '{rec.display_name}' confirmed in catalogue.",
        )

        print(f"\n[2] Authorization Gate: GRANTED (Ref: {auth.approval_reference})")

        # Step 4: Controlled Execution
        print(f"\n[3] Launching '{rec.display_name}' safely (shell=False)...")
        result = adapter.execute_application_launch(
            app_query_or_id=rec.app_id,
            task_id=task_id,
            authorization=auth,
            timeout_seconds=8.0,
        )

        print(f"\n[4] Execution Result:")
        print(f"    - Status: {result.status.upper()}")
        print(f"    - Verification Status: {result.verification_status}")
        print(f"    - Duration: {result.duration_ms} ms")
        if result.error_code:
            print(f"    - Error Code: {result.error_code}")
            print(f"    - Error Message: {result.error_message}")

        if result.verification:
            v = result.verification
            print(f"\n[5] Truthful Verification Evidence:")
            print(f"    - Verified: {v.verified}")
            print(f"    - Method: {v.method}")
            for k, val in v.details.items():
                print(f"      * {k}: {val}")

        if result.status == "completed":
            print(f"\n[SUCCESS] '{rec.display_name}' is verified open on your desktop.")
            close_it = input("Would you like to close it now? (y/N): ").strip().lower()
            if close_it in ("y", "yes"):
                adapter.cancel_action(result.action_id)
                print("[Closed] Terminated test application cleanly.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        adapter = WindowsAutomationAdapter()
        auth = AuthorizationDecision(
            decision_id="demo-dec",
            permission_status="granted",
            approval_reference="demo-ref",
            reason="Demo run",
        )
        res = adapter.execute_application_launch("Notepad", authorization=auth)
        print(f"Demo Run: status={res.status}, verified={res.verification.verified}")
        adapter.cancel_action(res.action_id)
    else:
        run_interactive()
