# AI Desktop Companion — Official Team Contracts & Task Roadmap

> **Document Version:** 2.0 (Leadership Transition & Test Release Edition)  
> **Team Lead:** Logeshwaran D (`@logeshwaran-dev05`)  
> **Project Repository:** [https://github.com/logeshwaran-dev05/AI-Desktop-Companion](https://github.com/logeshwaran-dev05/AI-Desktop-Companion)  
> **Target Release:** Test Version Delivery — **Tomorrow by 6:30 PM IST** (30-min buffer before 7:00 PM hard deadline)

---

## 1. Team Organization & Module Ownership

| Member | Role | Primary Module Directory | Core Technical Responsibility |
| :--- | :--- | :--- | :--- |
| **Logeshwaran D** | **Team Lead & Automation Architect** | `windows_automation/`, `desktop/electron/` | Universal application discovery, smart multi-path fallback, Win32 process verification, release packaging |
| **Madhan M** | **Frontend & Avatar Animation Lead** | `desktop/src/`, `desktop/public/` | Doraemon 8-frame walk cycle, taskbar docking UI, reactive expression states (Listening, Thinking, Success, Error) |
| **Hariram K S (Ram)** | **Senior Backend Orchestrator** | `api/` | FastAPI `/tasks` routes, async task lifecycle state machine, real-time polling/WebSocket sync, execution pipeline |
| **New Backend Engineer** | **Intent & Application Fallback Engine** | `ai_engine/`, `api/` | Top-50 Web/PWA application mappings, search query parameter extractor, end-to-end integration tests |
| **Booviha M** | **AI Engine Contributor** | `ai_engine/` | Prompt classification, Faster-Whisper voice transcription, plan step generation |

---

## 2. Release Timeline — Target Submission: 6:30 PM IST (Pure Working Product)

| Time (IST) | Milestone Goal | Expected Deliverable |
| :--- | :--- | :--- |
| **Tonight - 11:00 AM** | **Core Feature Completion** | Madhan finishes taskbar docking; Ram completes orchestrator status pipeline; New Dev finishes app/URL mappings. |
| **11:00 AM - 12:30 PM** | **Pull Request Sync & Review** | All feature branches pushed and PRs opened against `main`. Team Lead code review & merge. |
| **12:30 PM - 02:30 PM** | **End-to-End System Integration** | Connect Voice UI &rarr; Backend Orchestrator &rarr; Smart Fallback Launcher. |
| **02:30 PM - 04:30 PM** | **Live Real-World Testing** | Run `Launch-Companion.bat` on clean environments; test real Windows app launches + web fallbacks. |
| **04:30 PM - 06:00 PM** | **Zero-Bug Stability & Build Freeze** | Edge case fixes, crash prevention, process verification checks, and final one-click build packaging. |
| **06:00 PM - 06:30 PM** | **🚀 Working Product Submission** | Hand off tested, fully functional executable package to manager/evaluators. |
| **06:30 PM - 07:00 PM** | **Safety Buffer Window** | Safety margin for live walkthrough and evaluator verification. |

---

## 3. Detailed Teammate Contracts & Ready-to-Use Prompts

Each team member has a specific interface contract. Below are the exact instructions and a **copy-paste prompt** they can paste into their coding assistant or IDE to immediately start working.

---

### 👨‍💻 Contract 1: Madhan M (Frontend & Animations Lead)

* **Files Owned:**
  * `desktop/src/AvatarCharacter.tsx` (Doraemon animations & expressions)
  * `desktop/src/avatarAnimations.css` (CSS keyframes & particle effects)
  * `desktop/src/App.tsx` (Mission Control & desktop state)
  * `desktop/src/launchStateMachine.ts` (Client intent resolver)
* **Setup / Fetch Latest Code:**
  ```powershell
  git remote set-url origin https://github.com/logeshwaran-dev05/AI-Desktop-Companion.git
  git fetch origin
  git checkout -b feature/frontend-taskbar-docking origin/main
  ```
* **Task Objective:**
  1. Add a **"Taskbar Docking" visual mode**: When the companion is idle or seated, render Doraemon sitting or walking directly atop the bottom taskbar.
  2. Implement reactive expressions matching the backend task state:
     * `listening` &rarr; Ear waves / soundwave pulse.
     * `thinking` / `planning` &rarr; Bouncing thought bubble.
     * `success` &rarr; Celebration stars and happy jump.
     * `error` &rarr; Scratching head / exclamation mark.
  3. Ensure click-through works cleanly so the companion never blocks the user from clicking desktop icons or windows.
* **Verification Command:**
  ```powershell
  npm --prefix desktop run build
  ```

> 📋 **Copy-Paste Prompt for Madhan:**
> ```text
> Context: You are working on the AI Desktop Companion frontend (desktop/src/AvatarCharacter.tsx, desktop/src/App.tsx).
> Repo: https://github.com/logeshwaran-dev05/AI-Desktop-Companion
> 
> Task:
> 1. In desktop/src/AvatarCharacter.tsx, polish Doraemon's animations for the taskbar docking mode:
>    - Ensure smooth transitions across states: 'idle', 'walking', 'listening', 'thinking', 'success', 'error'.
>    - In 'listening' state, render subtle soundwave particles around Doraemon's ears.
>    - In 'success' state, show a celebratory bounce/stars.
> 2. Ensure desktop/src/launchStateMachine.ts maps 'youtube', 'spotify', 'netflix', 'chatgpt', 'github', 'gmail', 'notepad', 'calculator', 'explorer' into valid application intents.
> 3. Verify that running `npm run build` inside desktop/ passes with 0 TypeScript errors.
> ```

---

### 👨‍💻 Contract 2: Hariram K S / Ram (Senior Backend Orchestrator)

* **Files Owned:**
  * `api/main.py` (FastAPI router & lifecycle)
  * `api/orchestrator.py` (Task execution pipeline)
  * `api/schemas.py` (Request/Response DTOs)
  * `api/app_catalogue.py` (Backend registry)
* **Setup / Fetch Latest Code:**
  ```powershell
  git remote set-url origin https://github.com/logeshwaran-dev05/AI-Desktop-Companion.git
  git fetch origin
  git checkout -b feature/backend-orchestrator-integration origin/main
  ```
* **Task Objective:**
  1. Wire the `/tasks` endpoint in `api/main.py` directly to the `windows_automation` adapter.
  2. Maintain deterministic status updates:
     ```json
     {
       "task_id": "task_uuid",
       "status": "PENDING" | "PLANNING" | "EXECUTING" | "VERIFYING" | "COMPLETED" | "FAILED",
       "target": "YouTube",
       "execution_mode": "real",
       "verified": true,
       "error_message": null
     }
     ```
  3. Ensure that if `windows_automation` reports a web fallback (e.g. opened in Chrome), the task records `status="COMPLETED"`, `verified=true`, and notes `"Executed via Web Fallback"`.
* **Verification Command:**
  ```powershell
  python -m unittest api/tests/test_api_endpoints.py
  ```

> 📋 **Copy-Paste Prompt for Ram:**
> ```text
> Context: You are working on the AI Desktop Companion backend API (api/main.py, api/orchestrator.py).
> Repo: https://github.com/logeshwaran-dev05/AI-Desktop-Companion
> 
> Task:
> 1. In api/orchestrator.py, connect the task orchestrator to windows_automation.adapter.WindowsAutomationAdapter.
> 2. When a task request arrives (e.g. target="youtube" or action="open_application"):
>    - Execute the action through the adapter.
>    - Map the result to the response model:
>      status="COMPLETED" if result.status == "completed" or verified is True.
>      status="FAILED" with truthful error_code if execution failed.
> 3. Verify FastAPI starts without errors:
>    python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
> ```

---

### 👨‍💻 Contract 3: New Backend Engineer (Intent & Fallback Catalogue)

* **Files Owned:**
  * `ai_engine/planner/task_planner.py` (Command intent parser)
  * `ai_engine/schemas/command_schema.py` (Action schemas)
  * `desktop/electron/appLauncher.cjs` (Web fallback mapping reference)
* **Setup / Fetch Code (First-Time Onboarding):**
  ```powershell
  # 1. Clone our new repository:
  git clone https://github.com/logeshwaran-dev05/AI-Desktop-Companion.git
  cd AI-Desktop-Companion

  # 2. Create your feature branch:
  git checkout -b feature/backend-intent-fallbacks
  ```

> 📋 **Brief Onboarding Prompt for the New Backend Developer:**
> ```text
> Context:
> Welcome to the AI Desktop Companion team! We are building an interactive desktop assistant with a Smart Multi-Path Fallback Engine (it tries opening the native desktop app first; if not installed on the PC, it automatically opens the web service in Google Chrome/Edge, e.g. "Open YouTube" -> opens https://youtube.com in Chrome).
> 
> Your Task:
> 1. In ai_engine/planner/task_planner.py:
>    - Parse commands with target + search query parameters:
>      * "open <app>" -> target="<app>", action="open_application"
>      * "play <query> on youtube" -> target="youtube", action="search_web_app", parameters={"query": "<query>"}
>      * "search <query> on google" -> target="google", action="search_web_app", parameters={"query": "<query>"}
> 2. Expand intent mapping for the Top 50 popular apps:
>    - Media: YouTube, Spotify, Netflix, Prime Video, Disney+
>    - Productivity: Gmail, Google Drive, Docs, ChatGPT, Claude, Notion, Slack
>    - Developer: GitHub, GitLab, Stack Overflow, VS Code, Terminal
>    - Social: WhatsApp, LinkedIn, Twitter/X, Reddit
> 3. Run and verify tests:
>    python -m unittest discover -s ai_engine/tests
> ```

---

### 👨‍💻 Contract 4: Logeshwaran D (Team Lead & Automation Architect)

* **Files Owned:**
  * `windows_automation/`
  * `desktop/electron/`
  * `Launch-Companion.bat`
  * Repository releases & PR merges
* **Task Objective:**
  1. Maintain 100% passing tests on `windows_automation` (all 19 tests green).
  2. Implement smart multi-path execution in `appLauncher.cjs` (Native &rarr; Web URL &rarr; Web Search).
  3. Manage team branches, review pull requests, and ensure seamless one-click execution via `Launch-Companion.bat`.

---

## 4. Git Collaboration Rules for the Team

To prevent merge conflicts and ensure a professional development workflow:

1. **New Repository Remote**:
   Every member must configure their git remote to the new URL:
   ```powershell
   git remote set-url origin https://github.com/logeshwaran-dev05/AI-Desktop-Companion.git
   git fetch origin
   git branch --set-upstream-to=origin/main main
   ```

2. **Branch Naming Standard**:
   * Frontend: `feature/frontend-<feature-name>`
   * Backend: `feature/backend-<feature-name>`
   * AI Engine: `feature/ai-<feature-name>`
   * Automation: `feature/automation-<feature-name>`

3. **No Direct Pushes to `main`**:
   * Always branch out from `origin/main`.
   * Test your code locally before creating a Pull Request.
   * Open a PR into `main` and request review from `@logeshwaran-dev05`.

4. **Definition of Done (DoD) for Tomorrow 6:30 PM Submission**:
   * [ ] `Launch-Companion.bat` starts both backend and desktop UI without manual intervention.
   * [ ] Doraemon avatar appears smoothly on screen and docks on the taskbar.
   * [ ] Saying or typing *"Open YouTube"* opens YouTube in Chrome/Edge.
   * [ ] Saying or typing *"Open Notepad"* opens Windows Notepad and verifies in tasklist.
   * [ ] All tests pass: `python -m unittest discover -s windows_automation/tests`.
   * [ ] Zero uncaught exceptions in terminal logs.
