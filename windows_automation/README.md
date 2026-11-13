# Windows Automation & Universal Application Launching

**Developer:** Logeshwaran D (Windows Automation & Safe Execution, JM Vertex Technologies)  
**Team:** Team 2  
**Team Lead:** Vinay Vighnesh S  
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
│     ApplicationDiscoverer       │  Discovers apps from Registry (32 & 64 bit), Start Menu (.lnk),
└────────────────┬────────────────┘  App Paths, Get-StartApps (UWP/MSIX), and system built-ins.
                 │
                 ▼
┌─────────────────────────────────┐
│      ApplicationCatalogue       │  Indexes records, resolves names/aliases/IDs, handles whitespace,
└────────────────┬────────────────┘  deduplicates identical targets, and detects true ambiguity.
                 │
                 ▼
┌─────────────────────────────────┐
│       WindowsActionPolicy       │  Enforces allowlist, blocks arbitrary shell scripts & injection,
└────────────────┬────────────────┘  permits validated application launches safely.
                 │
                 ▼
┌─────────────────────────────────┐
│    WindowsAutomationExecutor    │  Selects launch method (EXE, shortcut, AppX, shell:AppsFolder),
└────────────────┬────────────────┘  captures diagnostic failures, tracks PIDs and idempotency.
                 │
                 ▼
┌─────────────────────────────────┐
│      WindowsWindowVerifier      │  Native Win32 EnumWindows / GetWindowThreadProcessId / Toolhelp32
└─────────────────────────────────┘  truthful process and GUI window readiness verification.
```

---

## 2. Supported Discovery Sources

The discovery engine (`ApplicationDiscoverer`) scans only reviewable, trusted Windows sources:
1. **Windows System Built-ins:** Core system utilities (`Notepad`, `Calculator`, `Paint`, `Task Manager`).
2. **Current-User Start Menu Shortcuts:** `%APPDATA%\Microsoft\Windows\Start Menu\Programs` (resolved via pure Python binary `.lnk` Shell Link parsing).
3. **All-Users Start Menu Shortcuts:** `%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs`.
4. **Windows App Paths Registry:**
   - `HKLM\Software\Microsoft\Windows\CurrentVersion\App Paths`
   - `HKLM\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\App Paths` (32-bit WOW64 node)
   - `HKCU\Software\Microsoft\Windows\CurrentVersion\App Paths`
5. **Windows Uninstall Registry Keys:**
   - `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall`
   - `HKLM\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall` (32-bit WOW64 node)
   - `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall`
6. **Windows StartApps & AppX/MSIX Packages:**
   - Windows `Get-StartApps` with caching, enumerating modern packaged applications (e.g. WhatsApp, Calculator, Spotify, Terminal) and Desktop Apps with Application User Model IDs (AUMIDs).
7. **WindowsApp Packaged Execution Aliases:**
   - `%LOCALAPPDATA%\Microsoft\WindowsApps` (UWP / MSIX application aliases).

---

## 3. Supported Application Types & Launch Methods

| Application Type | Launch Method | Description |
|---|---|---|
| **Normal Executable** | `subprocess_executable` | Directly invokes target binary using `subprocess.Popen(..., shell=False)` without shell injection. |
| **Start Menu Shortcut** | `start_menu_shortcut` | Safely invokes `.lnk` shortcut target using `os.startfile` delegating to Windows Shell. |
| **App Paths Registered** | `app_paths_registry` | Resolves target binary registered in App Paths and spawns safely via `subprocess.Popen`. |
| **AppX / MSIX Packaged** | `appx_packaged` | Spawns registered WindowsApp execution alias or AUMID without shell piping. |
| **Shell Apps Folder** | `shell_apps_folder` | Invokes modern desktop or packaged app via `os.startfile(r"shell:AppsFolder\" + aumid)`. |

*Arbitrary shell scripts (`.bat`, `.cmd`, `.ps1`, `.vbs`), directory traversal (`../`), and command chaining (`;`, `&`, `|`) are strictly rejected.*

---

## 4. Name & Alias Matching Behavior

The `ApplicationCatalogue.resolve(query)` method provides deterministic disambiguation:
- **Case-Insensitive & Whitespace Normalization:** Extra spaces and case differences are collapsed and normalized (e.g. `"   CHROME   "` → `"Google Chrome"`).
- **Exact ID Match:** Direct lookup by stable identifier (`app_id`).
- **Display Name Match:** Direct lookup by normalized display name.
- **Smart Alias Match:** Recognizes natural names (e.g., `"word"` → Microsoft Word, `"code"` → VS Code, `"calc"` → Calculator, `"wa"` → WhatsApp).
- **Publisher / Suffix Disambiguation:** Generic words like `microsoft` or `adobe` are treated as publisher prefixes rather than single-app aliases.
- **Binary Target Deduplication:** Multiple records pointing to the same binary (e.g., Start Menu shortcut vs raw App Paths entry for `winword.exe`) are deduplicated to the primary user-facing shortcut.
- **Ambiguity Detection:** Queries that match multiple distinct applications (e.g. `"Microsoft"` matching Word, Excel, Access, PowerPoint) return `status: "ambiguous"` with candidate suggestions rather than guessing.

---

## 5. Launch Verification Strategy

The `WindowsWindowVerifier` verifies execution outcomes using native Windows Win32 APIs (`EnumWindows`, `GetWindowThreadProcessId`, `IsWindowVisible`, `GetWindowTextW`, `GetClassNameW` via `ctypes`):
- **`launch_verified`:** Process is confirmed running AND top-level GUI window handle (`HWND`) is verified visible.
- **`launch_accepted`:** Launch command accepted and executed.
- **`verification_inconclusive`:** Process running, but window not detected within deadline (e.g. background utility or tray app).
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

- **Platform:** Windows 10 / Windows 11 (64-bit and 32-bit).
- **Python Version:** Python 3.10+ (tested on Python 3.11.9).
- **Dependencies:** Built entirely on Python standard library (`ctypes`, `winreg`, `struct`, `subprocess`, `dataclasses`, `time`). Zero third-party dependencies required.

---

## 8. Test Execution & Coverage

### Run All 26 Tests (Mocked, Live, & Packaged)
```powershell
python -m unittest discover -s windows_automation/tests -v
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

### Run Universal Packaged Application Tests (5 Tests)
```powershell
python -m unittest -v windows_automation/tests/test_universal_packaged_apps.py
```
Covers:
1. Packaged record creation and AUMID format validation.
2. WhatsApp resolution and natural voice alias matching.
3. Policy permits valid packaged applications.
4. Policy rejects malicious command injection tokens in packaged targets.
5. Controlled launch uses shell shortcut launcher without `shell=True`.

---

## 9. Actual Tested Application Report

| Application | Discovery Source | Launch Method | Result | Verification Evidence |
|---|---|---|---|---|
| Notepad | `start_apps` | `appx_packaged` | **PASS** | Process & Win32 GUI window verified |
| Calculator | `start_apps` | `appx_packaged` | **PASS** | UWP package AUMID target validated |
| Google Chrome | `start_apps` | `shell_apps_folder` | **PASS** | Discovered and target validated |
| WhatsApp | `start_apps` | `appx_packaged` | **PASS** | AUMID validated, launch adapter tested |
| Microsoft Word 2010 | `start_apps` | `shell_apps_folder` | **PASS** | Advertised shortcut resolved to `WINWORD.EXE` |
| Microsoft Excel 2010 | `app_paths` | `subprocess_executable` | **PASS** | Resolved via WOW64 App Paths |
| Microsoft PowerPoint 2010 | `start_apps` | `shell_apps_folder` | **PASS** | Resolved via StartApps desktop app |
| Paint | `appx_package` | `subprocess_executable` | **PASS** | WindowsApp execution alias resolved |
| Command Prompt | `start_menu_all_users` | `subprocess_executable` | **PASS** | Resolved shortcut to `cmd.exe` |
| Task Manager | `system_builtin` | `subprocess_executable` | **PASS** | System binary target verified |
| File Explorer | `start_apps` | `appx_packaged` | **PASS** | Shell application validated |
| Microsoft Edge | `start_apps` | `subprocess_executable` | **PASS** | Win32 browser target validated |
| Spotify | `start_apps` | `appx_packaged` | **PASS** | Packaged application target verified |
| Visual Studio Code | `start_apps` | `appx_packaged` | **PASS** | Code execution alias resolved |
| Adobe Photoshop 2025 | `start_apps` | `shell_apps_folder` | **PASS** | Desktop shortcut target validated |
| VLC media player | `start_menu_all_users` | `subprocess_executable` | **PASS** | Clean shortcut preferred over reset utilities |
| Microsoft (Query) | Discovery Index | Clarification Prompt | **PASS** | Ambiguity caught (30 candidates returned) |
| Adobe (Query) | Discovery Index | Clarification Prompt | **PASS** | Ambiguity caught (2 candidates returned) |
| NonExistentApp999 | N/A | N/A | **PASS** | Correctly rejected as `ERR_TARGET_NOT_FOUND` |
| notepad && calc | Security Policy | Blocked | **PASS** | Rejected as `ERR_TARGET_NOT_ALLOWLISTED` |

---

## 10. Unsupported Cases & Known Limitations

1. **Arbitrary Batch & Shell Scripts:**
   `.bat`, `.cmd`, `.ps1`, `.vbs`, and `.reg` scripts are explicitly rejected by policy for safety.
2. **Elevated (Administrator/UAC) Applications:**
   Applications that mandate administrative elevation (require UAC prompt) will launch with a Windows elevation dialog which requires physical user interaction; window verification will remain `launch_accepted` until the user accepts the UAC prompt.
3. **Background Services & CLI Utilities:**
   Console utilities without a graphical user interface (e.g. `ping`, `curl`) do not create persistent top-level windows; window verification correctly flags them as `verification_inconclusive` rather than fabricating GUI detection.
4. **Advertised MSI Shortcuts without Path Target:**
   Some legacy MSI advertised shortcuts store internal Darwin descriptors instead of raw executable paths; these are launched via `shell:AppsFolder` or Windows ShellExecute rather than raw `subprocess.Popen`.
