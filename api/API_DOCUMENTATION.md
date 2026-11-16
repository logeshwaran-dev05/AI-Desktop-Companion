# AI Desktop Companion — Backend API Documentation

**Module:** `api` (Backend & Task Orchestration)  
**Author:** Hariram K S  
**Technology Stack:** Python 3.11, FastAPI, Pydantic v2, Uvicorn  
**Milestone:** Validated & Verified Desktop Automation & Common Execution Pipeline  

---

## 1. Overview & Common Execution Pipeline

The Backend API coordinates natural language and voice input with the physical operating system. Both voice and text requests travel through a single shared execution service:

$$\text{User Input (Text / Voice)} \longrightarrow \text{Voice/Text Processing} \longrightarrow \text{AI Intent Extraction} \longrightarrow \text{App Matching} \longrightarrow \text{Windows Automation} \longrightarrow \text{Verification} \longrightarrow \text{Task Status}$$

### Key Architectural Guarantees:
1. **Shared Pipeline:** Voice input, voice transcripts, and text commands all invoke the identical task orchestrator service.
2. **Deterministic State Machine:** Tasks transition through discrete progress states: `listening` $\rightarrow$ `processing` $\rightarrow$ `matching` $\rightarrow$ `launching` $\rightarrow$ `launched` / `failed`.
3. **Truthful Win32 Verification (False Success Prevention):** A launch is **NEVER** marked as `launched` unless `WindowsAutomationAdapter` verifies window readiness and process creation.
4. **Safety & Policy Enforcement:** Only allowlisted applications (`Notepad`) can launch directly. Catalogue apps (`Calculator`, `Chrome`, `Paint`) pause for user confirmation (`requires_approval`). Unknown apps are rejected before dispatch.
5. **Idempotency Protection:** Duplicate requests with the same `idempotency_key` are rejected with `ERR_DUPLICATE_REQUEST` (HTTP 409).

---

## 2. Structured Task States

| State | Type | Description | Progress % |
|---|---|---|---|
| `listening` | Transient | Waiting for or receiving voice audio stream. | 10% |
| `processing` | Transient | Transcribing audio and extracting AI command intent. | 30% |
| `matching` | Transient | Resolving application identifiers against installed catalogue. | 50% |
| `requires_approval` | Intermediary | Paused for user approval (for catalogue apps). | 50% |
| `launching` | Transient | Dispatched to Windows Automation; polling Win32 window. | 75% |
| `launched` | **Terminal** | Process confirmed and top-level window verified by OS verifier. | 100% |
| `failed` | **Terminal** | Execution failed, timed out, or unverified. | 100% |
| `cancelled` | **Terminal** | Task aborted by user request or stop button. | 100% |

---

## 3. Standardized Error Codes

| Error Code | HTTP Status | Description |
|---|---|---|
| `ERR_TIMEOUT` | 504 / Task Result | Automation exceeded bounded timeout limit without window visibility. |
| `ERR_DUPLICATE_REQUEST` | 409 Conflict | Request with identical idempotency key already exists. |
| `ERR_VOICE_SERVICE_UNAVAILABLE` | 503 Unavailable | Microphone or voice transcription service is offline. |
| `ERR_UNKNOWN_APPLICATION` | 404 / 422 | Requested target is not in the installed catalogue or allowlist. |
| `ERR_INVALID_APPLICATION_ID` | 422 Unprocessable | Application identifier missing, empty, or contains forbidden characters. |
| `ERR_MISSING_PARAMETERS` | 422 Unprocessable | Required action parameter or target is missing. |
| `ERR_AMBIGUOUS_COMMAND` | 422 Unprocessable | Command matches multiple installed applications; clarification required. |
| `ERR_AUTOMATION_UNAVAILABLE` | 503 Unavailable | Windows Automation service or adapter is offline or unreachable. |
| `ERR_LAUNCH_FAILED` | 500 / Task Result | Subprocess spawn failed or executable missing. |
| `ERR_VERIFICATION_FAILED` | 500 / Task Result | Process spawned, but Win32 window was never verified. |
| `ERR_AUTOMATION_FAILURE` | 500 / Task Result | Windows Automation raised an unexpected OS error. |
| `ERR_INVALID_INTENT` | 422 Unprocessable | Planner could not extract a supported command intent. |
| `ERR_PERMISSION_DENIED` | 403 Forbidden | Security policy explicitly denied the request. |

---

## 4. API Endpoints Reference

### 4.1 Voice Input API
- **Endpoint:** `/voice/input`
- **Method:** `POST`
- **Purpose:** Receives raw or simulated voice audio data, checks service health, and initializes the pipeline in `listening` status.
- **Request Schema:**
  ```json
  {
    "audio_data": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA...",
    "format": "wav",
    "sample_rate": 16000,
    "simulate_service_down": false,
    "auto_execute": true,
    "idempotency_key": "voice_raw_001",
    "timeout_seconds": 10.0
  }
  ```
- **Response Schema (`202 Accepted`):**
  ```json
  {
    "task_id": "task_4df2998a-1a83-4a11-87ab-f06059d280b1",
    "status": "listening",
    "message": "Task initiated via voice.",
    "input_type": "voice"
  }
  ```
- **Example cURL:**
  ```bash
  curl -X POST http://127.0.0.1:8000/voice/input \
    -H "Content-Type: application/json" \
    -d '{"format": "wav", "simulate_service_down": false}'
  ```

---

### 4.2 Voice Transcript API
- **Endpoint:** `/voice/transcript`
- **Method:** `POST`
- **Purpose:** Submits recognized speech transcript directly into the shared execution pipeline.
- **Request Schema:**
  ```json
  {
    "transcript": "Open Notepad",
    "confidence": 0.98,
    "language": "en",
    "auto_execute": true,
    "idempotency_key": "voice_transcript_101",
    "timeout_seconds": 10.0
  }
  ```
- **Response Schema (`201 Created`):**
  ```json
  {
    "task_id": "task_2be2b1da-45c1-4b13-a41e-6dbbdf1ec192",
    "status": "launched",
    "transcript": "Open Notepad",
    "message": "Application 'Notepad' launched and verified successfully.",
    "input_type": "voice"
  }
  ```
- **Example cURL:**
  ```bash
  curl -X POST http://127.0.0.1:8000/voice/transcript \
    -H "Content-Type: application/json" \
    -d '{"transcript": "Open Notepad", "confidence": 0.99}'
  ```

---

### 4.3 Unified Task Submission API
- **Endpoint:** `/tasks/submit`
- **Method:** `POST`
- **Purpose:** Unified entrypoint for both text and voice commands.
- **Request Schema:**
  ```json
  {
    "command": "Open Notepad",
    "input_type": "text",
    "auto_execute": true,
    "idempotency_key": "req_sub_001",
    "timeout_seconds": 10.0
  }
  ```
- **Response Schema (`201 Created`):**
  ```json
  {
    "task_id": "task_9c1843b0-b541-4c17-9be7-ec562095f9d2",
    "input_type": "text",
    "command": "Open Notepad",
    "status": "launched",
    "message": "Application 'Notepad' launched and verified successfully."
  }
  ```
- **Example cURL:**
  ```bash
  curl -X POST http://127.0.0.1:8000/tasks/submit \
    -H "Content-Type: application/json" \
    -d '{"command": "Open Notepad", "input_type": "text"}'
  ```

---

### 4.4 Task Progress Update API
- **Endpoint:** `/tasks/{task_id}/progress`
- **Method:** `GET`
- **Purpose:** Polls real-time granular progress percentage, current stage, and chronological progress timeline.
- **Response Schema (`200 OK`):**
  ```json
  {
    "task_id": "task_9c1843b0-b541-4c17-9be7-ec562095f9d2",
    "status": "launched",
    "progress_percent": 100,
    "current_stage": "Application launched and verified on desktop",
    "timeline": [
      {
        "timestamp": "2026-11-03T18:15:00.100Z",
        "state": "processing",
        "message": "Processing input and extracting intent via AI Planner"
      },
      {
        "timestamp": "2026-11-03T18:15:00.120Z",
        "state": "matching",
        "message": "Resolving target application against installed catalogue."
      },
      {
        "timestamp": "2026-11-03T18:15:00.130Z",
        "state": "launching",
        "message": "Dispatching 'open_application' on 'Notepad' to Windows Automation."
      },
      {
        "timestamp": "2026-11-03T18:15:00.850Z",
        "state": "launched",
        "message": "Application 'Notepad' launched and verified successfully."
      }
    ],
    "message": "Application 'Notepad' launched and verified successfully."
  }
  ```
- **Example cURL:**
  ```bash
  curl -X GET http://127.0.0.1:8000/tasks/task_9c1843b0-b541-4c17-9be7-ec562095f9d2/progress
  ```

---

### 4.5 Final Task Result API
- **Endpoint:** `/tasks/{task_id}/result`
- **Method:** `GET`
- **Purpose:** Returns truthful execution outcome, Win32 window evidence, audit logs, and duration.
- **Response Schema (`200 OK`):**
  ```json
  {
    "task_id": "task_9c1843b0-b541-4c17-9be7-ec562095f9d2",
    "status": "launched",
    "result": {
      "action_id": "act_8a2d184e-9d22-44df-9118-e32047d10b77",
      "status": "completed",
      "duration_ms": 720
    },
    "message": "Application 'Notepad' launched and verified successfully.",
    "error_code": null,
    "verification": {
      "verified": true,
      "method": "win32_window_and_process_polling",
      "details": {
        "process_id": 14220,
        "process_name": "notepad.exe",
        "window_found": true,
        "window_title": "Untitled - Notepad",
        "window_handle": 67320
      },
      "evidence_timestamp": "2026-11-03T18:15:00.845Z"
    },
    "audit": {
      "event_type": "action_completed_verified",
      "redacted_summary": "Successfully launched and verified 'Notepad' (PID: 14220)"
    },
    "duration_ms": 720
  }
  ```
- **Example cURL:**
  ```bash
  curl -X GET http://127.0.0.1:8000/tasks/task_9c1843b0-b541-4c17-9be7-ec562095f9d2/result
  ```

---

### 4.6 Application Catalogue API
- **Endpoint:** `/catalogue` (and `/catalogue/{app_id}`)
- **Method:** `GET`
- **Purpose:** Returns all discovered installed applications, Windows built-in tools, Windows Settings pages, and Start Menu shortcuts.
- **Response Schema (`200 OK`):**
  ```json
  [
    {
      "app_name": "Notepad",
      "app_id": "notepad",
      "executable": "notepad.exe",
      "allowlisted": true
    },
    {
      "app_name": "Calculator",
      "app_id": "calculator",
      "executable": "calc.exe",
      "allowlisted": false
    },
    {
      "app_name": "Windows Settings",
      "app_id": "settings",
      "executable": "ms-settings:",
      "allowlisted": false
    }
  ]
  ```

---

## 5. Windows Application Catalogue

The backend maintains a dynamic `WindowsApplicationCatalogue` (module: `api/app_catalogue.py`) that extends the AI Engine's static catalogue with:

### 5.1 Supported Application Categories

| Category | Examples |
|---|---|
| **Windows Built-in Tools** | Notepad, Calculator, File Explorer, Task Manager, Control Panel, Paint, Command Prompt |
| **Windows Settings Pages** | Settings, System, Bluetooth, Display, Network, Sound, Apps, Windows Update |
| **Third-Party Applications** | Google Chrome, Visual Studio Code, Microsoft Edge, Visual Studio 2022 |
| **Registry App Paths** | Any application registered under `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths` |
| **Start Menu Shortcuts** | All `.lnk` files in ProgramData and AppData Start Menu directories |

### 5.2 Supported Applications Table

| `app_id` | `app_name` | `launch_target` | `launch_type` | Example Phrases |
|---|---|---|---|---|
| `notepad` | Notepad | `notepad.exe` | `built_in` | "Open Notepad", "Open text editor" |
| `calculator` | Calculator | `calc.exe` | `built_in` | "Open Calculator", "Open calc" |
| `explorer` | File Explorer | `explorer.exe` | `built_in` | "Open File Explorer", "Open files" |
| `taskmgr` | Task Manager | `taskmgr.exe` | `built_in` | "Open Task Manager", "Open processes" |
| `control` | Control Panel | `control.exe` | `built_in` | "Open Control Panel" |
| `paint` | Paint | `mspaint.exe` | `built_in` | "Open Paint", "Open drawing" |
| `cmd` | Command Prompt | `cmd.exe` | `built_in` | "Open terminal", "Open command prompt" |
| `settings` | Windows Settings | `ms-settings:` | `uri` | "Open Settings", "Open preferences" |
| `settings_system` | System Settings | `ms-settings:system` | `uri` | "Open System", "Go to system settings" |
| `settings_bluetooth` | Bluetooth Settings | `ms-settings:bluetooth` | `uri` | "Open Bluetooth settings", "Open paired devices" |
| `settings_display` | Display Settings | `ms-settings:display` | `uri` | "Open Display settings", "Open resolution" |
| `settings_network` | Network Settings | `ms-settings:network` | `uri` | "Open Network settings", "Open WiFi" |
| `settings_sound` | Sound Settings | `ms-settings:sound` | `uri` | "Open Sound settings", "Open volume" |
| `settings_apps` | Apps Settings | `ms-settings:appsfeatures` | `uri` | "Open installed apps", "Open apps" |
| `settings_update` | Windows Update | `ms-settings:windowsupdate` | `uri` | "Open Windows Update", "Check for updates" |
| `chrome` | Google Chrome | `chrome.exe` | `executable` | "Open Chrome", "Launch Chrome", "Open browser", "Can you open my browser?" |
| `vscode` | Visual Studio Code | `code.exe` | `executable` | "Open VS Code", "Open code editor", "Open Visual Studio Code" |
| `edge` | Microsoft Edge | `msedge.exe` | `executable` | "Open Edge", "Open Microsoft Edge" |
| `visualstudio2022` | Visual Studio 2022 | `devenv.exe` | `executable` | "Open Visual Studio 2022", "Open VS IDE" |

### 5.3 Natural Language Phrase Resolution

The resolver strips common verb prefixes before matching:
- **Stripped prefixes:** `open`, `launch`, `start`, `go to`, `navigate to`, `show me`, `take me to`, `please open`, `can you open`, `could you open`, `would you open`

**Example phrase mappings:**

| User Phrase | Resolved `app_id` |
|---|---|
| "Open Chrome" | `chrome` |
| "Launch Chrome" | `chrome` |
| "Start Google Chrome" | `chrome` |
| "Can you open my browser?" | `chrome` |
| "Open Settings" | `settings` |
| "Go to System" | `settings_system` |
| "Open Bluetooth settings" | `settings_bluetooth` |
| "Open Display Settings" | `settings_display` |
| "Open WiFi" | `settings_network` |
| "Open VS Code" | `vscode` |
| "Open my code editor" | `vscode` |
| "Open Calculator" | `calculator` |
| "Open File Explorer" | `explorer` |
| "Open Task Manager" | `taskmgr` |

### 5.4 Ambiguity Handling

Ambiguous queries (e.g., "Open Visual Studio") that match both **Visual Studio Code** and **Visual Studio 2022** are:
1. Detected by `is_ambiguous()` before execution.
2. Returned to the user as `ERR_AMBIGUOUS_COMMAND` with a clarification request.
3. Never silently routed to the wrong application.

### 5.5 Structured Command Request Format

After catalogue resolution, the backend builds a `StructuredActionRequest` for Windows Automation:

```json
{
  "action": "launch_application",
  "application_id": "chrome",
  "target": "Google Chrome",
  "parameters": {},
  "source": "voice"
}
```

```json
{
  "action": "launch_application",
  "application_id": "settings_bluetooth",
  "target": "Bluetooth Settings",
  "parameters": {},
  "source": "text"
}
```

---

## 6. Error Codes Reference (Extended)

| Error Code | HTTP Status | Description |
|---|---|---|
| `ERR_TIMEOUT` | 504 / Task Result | Automation exceeded bounded timeout limit without window visibility. |
| `ERR_DUPLICATE_REQUEST` | 409 Conflict | Request with identical idempotency key already exists. |
| `ERR_VOICE_SERVICE_UNAVAILABLE` | 503 Unavailable | Microphone or voice transcription service is offline. |
| `ERR_UNKNOWN_APPLICATION` | 404 / 422 | Requested target is not in the installed catalogue or allowlist. |
| `ERR_INVALID_APPLICATION_ID` | 422 Unprocessable | Application identifier missing, empty, or contains forbidden characters. |
| `ERR_MISSING_PARAMETERS` | 422 Unprocessable | Required action parameter or target is missing. |
| `ERR_AMBIGUOUS_COMMAND` | 422 Unprocessable | Command matches multiple installed applications; clarification required. |
| `ERR_AUTOMATION_UNAVAILABLE` | 503 Unavailable | Windows Automation service or adapter is offline or unreachable. |
| `ERR_LAUNCH_FAILED` | 500 / Task Result | Subprocess spawn failed or executable missing. |
| `ERR_VERIFICATION_FAILED` | 500 / Task Result | Process spawned, but Win32 window was never verified. |
| `ERR_AUTOMATION_FAILURE` | 500 / Task Result | Windows Automation raised an unexpected OS error. |
| `ERR_INVALID_INTENT` | 422 Unprocessable | Planner could not extract a supported command intent. |
| `ERR_PERMISSION_DENIED` | 403 Forbidden | Security policy explicitly denied the request. |
| `ERR_TARGET_NOT_ALLOWLISTED` | 403 / Task Result | Windows Automation policy rejected the target — coordinate with Logeshwaran to expand allowlist. |
| `ERR_CANCELLED` | — / Task Result | Task was cancelled by user or stop button. |

---

## 7. Running the API Server & Tests

### Start Server
```powershell
# Using the workspace virtual environment
.\.venv\Scripts\python.exe api/main.py
```
*(Runs on `http://127.0.0.1:8000` with interactive Swagger docs at `http://127.0.0.1:8000/docs`).*

### Run Integration & Unit Tests
```powershell
# Run all tests in the workspace (110+ tests after Priority 4 suite)
python -m unittest discover -s . -p "test_*.py"

# Run Priority 4 — Application Catalogue & Orchestration tests (18 tests)
python -m unittest api.tests.test_app_catalogue_orchestration -v

# Run Priority 3 AI Intent + Windows Automation Integration tests (14 tests)
python -m unittest api.tests.test_priority3_integration -v

# Run Common Pipeline Integration tests
python -m unittest api.tests.test_common_pipeline -v

# Run Live Windows End-to-End Test
python -m unittest api.tests.test_live_orchestration -v

# Run Pyright static type analysis
npx --yes pyright api api/tests
```

