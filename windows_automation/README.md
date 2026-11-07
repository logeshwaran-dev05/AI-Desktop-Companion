# Windows Automation & Universal Application Launching

**Created by:** Logeshwaran D (Windows Automation & Safe Execution, JM Vertex Technologies)  
**Module:** `windows_automation`  
**Milestone:** Complete Windows Automation & Universal App Launching  
**Repository:** `https://github.com/Vinayvighnesh2008/AI-Desktop-Companion`

---

## 1. Overview & Architecture

The `windows_automation` module provides a hardened, auditable execution and discovery layer for Windows desktop automation. It dynamically discovers installed Windows software across trusted sources, indexes them into a safe application catalogue, and executes application launches via type-specific methods with Win32 verification, diagnostics, and strict security policy gating.

```
[ User Input / Voice / AI Planner ]
                 │
                 ▼
       [ Application Query ]
                 │
                 ▼
┌─────────────────────────────────┐
│     ApplicationDiscoverer       │  Discovers apps from Registry, Start Menu (.lnk),
└────────────────┬────────────────┘  App Paths, AppX aliases, and system built-ins.
                 │
                 ▼
┌─────────────────────────────────┐
│      ApplicationCatalogue       │  Indexes records, resolves names/aliases/IDs,
└────────────────┬────────────────┘  handles whitespace, and detects ambiguity.
                 │
                 ▼
┌─────────────────────────────────┐
│       WindowsActionPolicy       │  Enforces allowlist, blocks arbitrary shell scripts,
└────────────────┬────────────────┘  allows validated launches without manual prompt.
                 │
                 ▼
┌─────────────────────────────────┐
│    WindowsAutomationExecutor    │  Selects launch method (EXE, shortcut, AppX),
└────────────────┬────────────────┘  captures diagnostic failures, tracks PIDs.
                 │
                 ▼
┌─────────────────────────────────┐
│      WindowsWindowVerifier      │  Native Win32 EnumWindows / GetWindowThreadProcessId
└─────────────────────────────────┘  truthful window readiness verification.
```

---

## 2. Supported Discovery Sources

The discovery engine (`ApplicationDiscoverer`) scans only reviewable, trusted Windows sources:
1. **Windows System Built-ins:** Core system utilities (`Notepad`, `Calculator`, `Paint`, `Task Manager`).
2. **Current-User Start Menu Shortcuts:** `%APPDATA%\Microsoft\Windows\Start Menu\Programs` (resolved via pure Python binary `.lnk` Shell Link parsing).
3. **All-Users Start Menu Shortcuts:** `%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs`.
4. **Windows App Paths Registry:**
   - `HKLM\Software\Microsoft\Windows\CurrentVersion\App Paths`
   - `HKCU\Software\Microsoft\Windows\CurrentVersion\App Paths`
5. **Windows Uninstall Registry Keys:**
   - `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall`
   - `HKLM\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall`
   - `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall`
6. **WindowsApp Packaged Execution Aliases:**
   - `%LOCALAPPDATA%\Microsoft\WindowsApps` (UWP / MSIX application aliases like Windows Terminal, Notepad modern, etc.).

---

## 3. Supported Application Types & Launch Methods

| Application Type | Launch Method | Description |
|---|---|---|
| **Normal Executable** | `subprocess_executable` | Directly invokes target binary using `subprocess.Popen(..., shell=False)`. |
| **Start Menu Shortcut** | `start_menu_shortcut` | Safely invokes `.lnk` shortcut target using `os.startfile` or resolved target. |
| **App Paths Registered** | `app_paths_registry` | Resolves target binary registered in App Paths and spawns safely. |
| **AppX / MSIX Packaged** | `appx_packaged` | Spawns registered WindowsApp execution alias or AUMID without shell piping. |

*Arbitrary shell scripts (`.bat`, `.cmd`, `.ps1`, `.vbs`), directory traversal (`../`), and command chaining (`;`, `&`, `|`) are strictly rejected.*

---

## 4. Name & Alias Matching Behavior

The `ApplicationCatalogue.resolve(query)` method provides deterministic disambiguation:
- **Case-Insensitive & Whitespace Normalization:** Extra spaces and case differences are collapsed and normalized (e.g. `"   CHROME   "` → `"Google Chrome"`).
- **Exact ID Match:** Direct lookup by stable identifier (`app_id`).
- **Display Name Match:** Direct lookup by normalized display name.
- **Exact Alias Match:** Keywords like `"calc"`, `"text editor"`, `"web browser"`.
- **Partial / Prefix Matching:** Safely resolves single candidates; detects when multiple candidates match (e.g. `"vs"` matching both Visual Studio and VS Code).
- **Ambiguity Detection:** Returns status `"ambiguous"` with the list of candidates rather than guessing.

---

## 5. Launch Verification Strategy

The `WindowsWindowVerifier` verifies execution outcomes using native Windows Win32 APIs (`EnumWindows`, `GetWindowThreadProcessId`, `IsWindowVisible`, `GetWindowTextW`, `GetClassNameW` via `ctypes`):
- **`launch_verified`:** Process is running AND top-level GUI window handle (`HWND`) confirmed visible.
- **`launch_accepted`:** Launch command accepted and executed.
- **`verification_inconclusive`:** Process running, but window not detected within deadline (e.g. background utility).
- **`timed_out`:** Verification deadline expired and process terminated.
- **`launch_failed`:** Process exited or crashed immediately after launch.
- **`cancelled` / `denied`:** Aborted at authorization or cancellation checkpoint.

---

## 6. Diagnostic Information on Failure

For every launch failure, `DiagnosticRecord` captures:
- `requested_target`: Input target name.
- `resolved_app_id`: Canonical application ID.
- `discovery_source`: Source where the app was found.
- `launch_method`: Launch method chosen.
- `target_validation_passed`: Boolean validation flag.
- `failing_stage`: `"validation"`, `"authorization"`, `"target_resolution"`, `"launch_spawn"`, or `"verification"`.
- `exception_details`: Cleaned error message (sensitive tokens redacted).
- `verification_summary`: Output details from the window verifier.

---

## 7. Setup & Dependencies

- **Platform:** Windows 10 / Windows 11 (64-bit).
- **Python Version:** Python 3.10+ (tested on Python 3.11.9).
- **Dependencies:** Built entirely on Python standard library (`ctypes`, `winreg`, `struct`, `subprocess`, `dataclasses`, `time`). Zero third-party dependencies required.

---

## 8. Test Execution & Coverage

### Run All 21 Tests (Mocked & Live)
```powershell
python -m unittest discover -s windows_automation/tests
```

### Run Mocked Unit Tests (15 Tests)
```powershell
python -m unittest -v windows_automation/tests/test_windows_automation_mocked.py
```
Covers:
1. Application discovery across sources.
2. Duplicate applications handling.
3. Missing applications.
4. Invalid targets & script extensions.
5. Normal EXE launch.
6. Start Menu shortcut launch.
7. Packaged application launch (AppX / Execution Alias).
8. Alias matching and whitespace handling.
9. Ambiguous application names.
10. Launch failures & diagnostics.
11. Verification success and failure / timeout.
12. Permission and safety behavior.
13. Repeated requests / idempotency deduplication.
14. Existing typed-command regression (Notepad).
15. Integration with the existing workflow (Booviha's PlanStep adapter).

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
6. End-to-end integration with Booviha's `PlanStep`.
