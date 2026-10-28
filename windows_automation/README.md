# Windows Automation — Installed Application Discovery & Safe Launch

**Created by:** Logeshwaran D (Windows Automation — Safe Actions & Verification, JM Vertex Technologies)  
**Module:** `windows_automation`  
**Milestone:** Complete 27–30 October 2026 Tasks (Discovery, Catalogue Resolution, Safe Launch & Verification)  
**Repository:** `https://github.com/Vinayvighnesh2008/AI-Desktop-Companion`

---

## 1. Overview & Architecture

The `windows_automation` module provides an auditable, secure execution and discovery layer for Windows desktop automation. It discovers installed Windows software across trusted sources, indexes them into a safe application catalogue, and executes controlled application launches with Win32 verification and strict security policy gating.

```
[ User Input / AI Planner ]
             │
             ▼
   [ Application Query ]
             │
             ▼
┌─────────────────────────┐
│   ApplicationDiscoverer │  Discovers apps from Registry, Start Menu (.lnk), and built-ins.
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   ApplicationCatalogue  │  Indexes records, resolves names/aliases/IDs, handles ambiguity.
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   WindowsActionPolicy   │  Enforces allowlist, blocks arbitrary shell scripts, verifies auth.
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ WindowsAutomationExecutor│ Spawns process (shell=False), tracks PID, enforces cancellation.
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  WindowsWindowVerifier  │  Win32 EnumWindows / GetWindowThreadProcessId verification.
└─────────────────────────┘
```

---

## 2. Supported Discovery Sources

The discovery engine (`ApplicationDiscoverer`) scans only reviewable, trusted Windows sources:
1. **Windows System Built-ins:** Core system utilities (`Notepad`, `Calculator`, `Paint`).
2. **Current-User Start Menu Shortcuts:** `%APPDATA%\Microsoft\Windows\Start Menu\Programs` (resolved via pure Python binary `.lnk` Shell Link parsing).
3. **All-Users Start Menu Shortcuts:** `%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs`.
4. **Windows Registry (Installed Software):**
   - `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall`
   - `HKLM\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall`
   - `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall`

---

## 3. Catalogue Fields & Identifier Format

Every application record (`ApplicationRecord`) contains:
- **`app_id`**: Deterministic slug identifier (e.g. `app_google_chrome`, `app_notepad`, `app_microsoft_edge`).
- **`display_name`**: Official human-readable application name (e.g. `"Google Chrome"`).
- **`normalized_name`**: Normalized lowercase search string (e.g. `"google chrome"`).
- **`executable_path`**: Validated filesystem path to target `.exe` or system binary.
- **`source`**: Discovery origin (`"system_builtin"`, `"start_menu_user"`, `"start_menu_all_users"`, `"registry"`).
- **`status`**: `"available"` (executable verified on disk) or `"target_missing"`.
- **`version` / `publisher` / `icon_path`**: Optional trustworthy metadata.
- **`aliases`**: Alternate search keywords (e.g. `["chrome", "google chrome"]`).

---

## 4. Target Resolution & Validation

The `ApplicationCatalogue.resolve(query)` method provides deterministic disambiguation:
- **Exact Matches:** Direct match against `app_id`, `normalized_name`, or exact alias → `"resolved"`.
- **Ambiguous Matches:** If a query matches multiple applications (e.g. "Visual Studio" matching both VS and VS Code) → `"ambiguous"` with candidate list.
- **Missing Applications:** Query not found → `"not_found"`.
- **Pre-Launch Validation:** Immediately before execution, the executor verifies that the target executable exists and has a permitted `.exe` extension. Prohibits scripts (`.bat`, `.cmd`, `.ps1`, `.vbs`, `.sh`) and raw shell strings.

---

## 5. Security & Permission Enforcement

1. **Authorization Gate:** An action cannot execute without an `AuthorizationDecision` having `permission_status="granted"`.
2. **Approval Enforcement:** If `requires_user_approval=True`, a valid `approval_reference` must be provided.
3. **No Shell Invocations:** All executions use `subprocess.Popen(..., shell=False)` without elevated admin privileges.
4. **Idempotency & Duplicate Prevention:** Identical requests within a task lifecycle are deduplicated (`ERR_DUPLICATE_REQUEST`).
5. **Pre & Post-Launch Cancellation:** Cancelling an action terminates the spawned process (including child app alias PIDs) and confirms termination.

---

## 6. Truthful Launch Verification

The `WindowsWindowVerifier` verifies execution outcomes using native Windows Win32 APIs (`EnumWindows`, `GetWindowThreadProcessId`, `IsWindowVisible`, `GetWindowTextW`, `GetClassNameW` via `ctypes`):
- **`launch_verified`:** Process is running AND top-level GUI window handle (`HWND`) confirmed visible.
- **`verification_inconclusive`:** Process running, but window not detected within deadline.
- **`timed_out`:** Verification deadline expired and process terminated.
- **`launch_failed`:** Process exited or crashed immediately after launch.
- **`cancelled` / `denied`:** Aborted at authorization or cancellation checkpoint.

---

## 7. Setup & Dependencies

- **Platform:** Windows 10 / Windows 11 (64-bit).
- **Python Version:** Python 3.10+ (tested on Python 3.11.9).
- **Dependencies:** Built entirely on Python standard library (`ctypes`, `winreg`, `struct`, `subprocess`, `dataclasses`, `time`). Zero third-party dependencies required.

---

## 8. Test Execution & Coverage

### Run All 25 Tests (Mocked & Live)
```powershell
python -m unittest discover -s windows_automation/tests
```

### Run Mocked Unit Tests (19 Tests)
```powershell
python -m unittest -v windows_automation/tests/test_windows_automation_mocked.py
```
Covers:
1. Discovery across sources.
2. Duplicate entry handling.
3. Inaccessible/missing discovery directories.
4. Empty catalogue vs failure.
5. Valid target resolution.
6. Ambiguous and missing target resolution.
7. Controlled launch.
8. Launch failure handling.
9. Permission denied.
10. Missing approval.
11. Pre-launch cancellation.
12. Post-launch cancellation.
13. Duplicate request deduplication.
14. Timeout handling.
15. Verification success.
16. Verification failure/inconclusive evidence.
17. Rejection of arbitrary shell commands.
18. Audit log credential redaction.
19. Regression tests for existing AI Planner PlanStep.

### Run Live Windows Integration Tests (6 Tests)
```powershell
python -m unittest -v windows_automation/tests/test_windows_automation_live.py
```
Covers:
1. Real Windows application discovery (scans actual Registry & Start Menu).
2. Live catalogue resolution.
3. Real Notepad launch and Win32 window detection.
4. Controlled launch via catalogue record.
5. Rejection of dangerous shell command targets.
6. End-to-end integration with Booviha's `ai_engine.schemas.command_schema.PlanStep`.
