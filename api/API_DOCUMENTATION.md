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
    }
  ]
  ```

---

## 5. Running the API Server & Tests

### Start Server
```powershell
python api/main.py
```
*(Runs on `http://127.0.0.1:8000` with interactive Swagger docs at `http://127.0.0.1:8000/docs`).*

### Run Integration & Unit Tests
```powershell
# Run all tests in the workspace (78 tests)
python -m unittest discover -s . -p "test_*.py"

# Run Common Pipeline Integration tests
python -m unittest api/tests/test_common_pipeline.py

# Run Live Windows End-to-End Test
python -m unittest api/tests/test_live_orchestration.py
```

