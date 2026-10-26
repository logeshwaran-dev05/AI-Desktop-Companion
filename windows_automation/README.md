# Windows Automation — Safe Actions & Verification

**Created by:** Logeshwaran D (Windows Automation — Safe Actions & Verification, JM Vertex Technologies)  
**Module:** `windows_automation`  
**Milestone:** Milestone 1 — Validated & Verified "Open Notepad" Launch  
**Repository:** `https://github.com/Vinayvighnesh2008/AI-Desktop-Companion`

---

## 1. Overview & Architecture

The `windows_automation` module provides a hardened, secure execution layer for Windows desktop automation. It bridges AI-generated action plans and backend tasks with the physical operating system while guaranteeing safety, explicit allowlisting, and verifiable execution outcomes.

### Architecture Components

1. **`schemas.py`**:
   - `ActionRequest`: Strongly typed action payload with task IDs, bounded timeouts, and security authorization metadata.
   - `AuthorizationDecision`: Explicit permission and user approval record.
   - `VerificationEvidence`: Truthful process and window visibility evidence.
   - `ExecutionResult`: Structured outcome returned to caller.
   - `AuditRecord`: Redacted security audit trail event.

2. **`policy.py` (`WindowsActionPolicy`)**:
   - Explicit application allowlist (`Notepad` / `notepad.exe` in Milestone 1).
   - Strict rejection of arbitrary executable paths, shell scripts, directory traversal, and command chaining tokens (`;`, `&`, `|`, `powershell`, `cmd.exe`).
   - Permission verification: Never invents approvals. Disallows execution if permissions are missing or denied.

3. **`verifier.py` (`WindowsWindowVerifier`)**:
   - Distinguishes raw process creation from verified GUI window readiness.
   - Uses native Windows Win32 API (`EnumWindows`, `GetWindowThreadProcessId`, `IsWindowVisible`, `GetWindowTextW`, `GetClassNameW` via `ctypes`).
   - Accurately supports both traditional Win32 processes and modern Windows 10/11 packaged UWP App Execution Aliases (where the spawned stub delegates to the packaged Notepad process).
   - Never fabricates verification evidence.

4. **`executor.py` (`WindowsAutomationExecutor`)**:
   - Safe subprocess execution using `subprocess.Popen(..., shell=False)`.
   - Process tracking and cancellation support (`cancel(action_id)` cleanly terminates spawned processes and verifies exit).
   - Duplicate request detection using idempotency keys (`ERR_DUPLICATE_REQUEST`).
   - Clean cleanup on verification timeout to prevent orphaned/zombie processes.

5. **`audit.py` (`AuditLogger`)**:
   - Records structured lifecycle events for every action.
   - Automatic redaction of sensitive tokens, credentials, passwords, and bearer tokens.
   - Strictly does NOT take screenshots or capture clipboard data.

6. **`adapter.py` (`WindowsAutomationAdapter`)**:
   - Narrow compatibility adapter connecting Booviha's `ai_engine.schemas.command_schema.PlanStep` or raw dictionaries to the Windows executor.

---

## 2. Supported Actions (Milestone 1)

| Action Name | Target | Parameters | Description |
|---|---|---|---|
| `open_application` | `"Notepad"` / `"notepad.exe"` | `args: []` | Launches allowlisted Windows Notepad and verifies top-level window visibility. |

*Any other action name or unallowlisted target (e.g., `calc.exe`, `cmd.exe`, `explorer.exe`) is rejected with `ERR_UNSUPPORTED_ACTION` or `ERR_TARGET_NOT_ALLOWLISTED`.*

---

## 3. Permission & Safety Rules

1. **Authorization Gate:** An action cannot execute without an `AuthorizationDecision` having `permission_status="granted"`.
2. **Approval Enforcement:** If `requires_user_approval=True`, an `approval_reference` must be provided. Missing approvals fail with `ERR_MISSING_APPROVAL`.
3. **No Elevated Privileges:** Processes are spawned under user privileges without elevation or unrestricted shell execution.
4. **No Destructive Retries:** Failed or cancelled actions are never retried automatically.
5. **Deduplication:** Repeated requests with identical idempotency keys are blocked to prevent duplicate window spawns.

---

## 4. Setup & Dependencies

- **Operating System:** Windows 10 / Windows 11 (64-bit).
- **Python Version:** Python 3.10+ (tested with Python 3.11.9).
- **External Dependencies:** Zero required third-party packages for core execution (built entirely on Python standard library: `ctypes`, `subprocess`, `dataclasses`, `time`, `re`).

---

## 5. Running Tests

The test suite separates mocked unit tests from real Windows integration tests:

### A. Run Mocked Unit Tests (10/10 Core Scenarios)
Tests execution, timeouts, cancellations, permissions, and redaction in an isolated mocked environment:
```powershell
python -m unittest windows_automation/tests/test_windows_automation_mocked.py
```

### B. Run Live Windows Integration Tests
Tests real Notepad launch, Win32 window verification, and process cleanup on Windows:
```powershell
python -m unittest windows_automation/tests/test_windows_automation_live.py
```

### C. Run All Tests
```powershell
python -m unittest discover -s windows_automation/tests
```

---

## 6. Known Limitations & Future Work

- **Scope:** Milestone 1 is intentionally scoped to `"open_application"` with `"Notepad"`. Browser automation, shell scripts, and keyboard/mouse injection are intentionally disabled until team review.
- **Contract Agreement:** Pending final review of `shared/TEAM_CONTRACTS.md` with Vinay Vighnesh S (Desktop Integration Lead) and Hariram K S (Backend API Owner).
