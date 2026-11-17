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

## 2. Release Timeline — Target Submission: 6:30 PM IST

| Time (IST) | Milestone Goal | Expected Deliverable |
| :--- | :--- | :--- |
| **Tonight - 11:00 AM** | **Core Feature Completion** | Madhan finishes taskbar docking; Ram completes orchestrator status pipeline; New Dev finishes app/URL mappings. |
| **11:00 AM - 12:30 PM** | **Pull Request Sync & Review** | All feature branches pushed and PRs opened against `main`. Team Lead code review. |
| **12:30 PM - 02:30 PM** | **End-to-End System Integration** | Connect Voice UI &rarr; Backend Orchestrator &rarr; Smart Fallback Launcher. |
| **02:30 PM - 04:30 PM** | **Regression Testing & Bug Squash** | Full test runs using `Launch-Companion.bat`. Zero crash tolerance on common voice/text queries. |
| **04:30 PM - 05:45 PM** | **Demo Recording & Documentation** | Record 2-minute video demonstrating desktop walking, taskbar docking, and opening YouTube/Notepad. |
| **06:00 PM - 06:30 PM** | **🚀 Final Test Version Submission** | Tag release `v0.1.0-test` and submit to manager/evaluators (ahead of 7 PM). |
| **06:30 PM - 07:00 PM** | **Buffer Window** | Safety margin for any unexpected deployment or connectivity hiccups. |

---

## 3. Detailed Teammate Contracts & Ready-to-Use Prompts

Each team member has a specific interface contract. Below are the exact instructions and a **copy-paste prompt** they can paste into their coding assistant or IDE to immediately start working.

---

### 👨‍💻 Contract 1: Madhan M (Frontend & Animations Lead)

* **Files Owned:**
  * `desktop/src/AvatarCharacter.tsx`
  * `desktop/src/avatarAnimations.css`
  * `desktop/src/App.tsx`
  * `desktop/src/launchStateMachine.ts`
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

> 📋 **Prompt for Madhan to paste in his IDE:**
> ```text
> You are working on the AI Desktop Companion frontend (desktop/src/AvatarCharacter.tsx, desktop/src/App.tsx).
> Task:
> 1. Polish the Doraemon avatar animations for the taskbar docking state:
>    - Ensure the avatar smoothly transitions between states: 'idle', 'walking', 'listening', 'thinking', 'success', 'error'.
>    - In 'listening' state, show subtle soundwave particles or ear glow.
>    - In 'success' state, show a celebratory bounce.
> 2. Ensure desktop/src/launchStateMachine.ts maps 'youtube', 'spotify', 'netflix', 'chatgpt', 'github', 'gmail', 'notepad', 'calculator', 'explorer' into valid application intents.
> 3. Verify that running `npm run build` inside desktop/ passes without any TypeScript errors.
> ```

---

### 👨‍💻 Contract 2: Hariram K S / Ram (Senior Backend Orchestrator)

* **Files Owned:**
  * `api/main.py`
  * `api/orchestrator.py`
  * `api/schemas.py`
  * `api/app_catalogue.py`
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

> 📋 **Prompt for Ram to paste in his IDE:**
> ```text
> You are working on the AI Desktop Companion backend API (api/main.py, api/orchestrator.py).
> Task:
> 1. Connect the task orchestrator in api/orchestrator.py to windows_automation.adapter.WindowsAutomationAdapter.
> 2. When a task request arrives (e.g. target="youtube" or action="open_application"):
>    - Execute the action through the adapter.
>    - Accurately map the result to the response model:
>      status="COMPLETED" if result.status == "completed" or verified is True.
>      status="FAILED" with truthful error_code if execution failed.
> 3. Ensure FastAPI starts cleanly without import errors when launched via:
>    python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
> ```

---

### 👨‍💻 Contract 3: New Backend Engineer (Intent & Fallback Catalogue)

* **Files Owned:**
  * `ai_engine/planner/task_planner.py`
  * `ai_engine/schemas/command_schema.py`
  * `desktop/electron/appLauncher.cjs`
* **Task Objective:**
  1. Expand the URL and search catalogue for the **Top 50 common applications & services**:
     * Media: YouTube, Spotify, Netflix, Prime Video, Disney+, Twitch, SoundCloud.
     * Productivity: Gmail, Google Drive, Google Docs, Notion, Slack, Teams, ChatGPT, Claude.
     * Developer: GitHub, GitLab, Stack Overflow, VS Code, Terminal.
     * Social: WhatsApp, LinkedIn, Twitter/X, Reddit, Instagram.
  2. Entity extraction:
     * If user says *"play lofi beats on youtube"*, extract `target="youtube"`, `query="lofi beats"`, so the launcher opens:
       `https://www.youtube.com/results?search_query=lofi+beats`
     * If user says *"search best python tutorials"*, extract `target="google"`, `query="best python tutorials"`.
  3. Write test cases validating entity extraction and URL mapping.
* **Verification Command:**
  ```powershell
  python -m unittest ai_engine/tests/test_planner.py
  ```

> 📋 **Prompt for New Backend Dev to paste in their IDE:**
> ```text
> You are working on the AI Engine and Intent Mapping (ai_engine/planner/task_planner.py, ai_engine/schemas/command_schema.py).
> Task:
> 1. Enhance task_planner.py to parse complex commands with parameters:
>    - "open <app>" -> target=<app>, action="open_application"
>    - "play <query> on youtube" -> target="youtube", action="search_web_app", parameters={"query": "<query>"}
>    - "search <query> on google" -> target="google", action="search_web_app", parameters={"query": "<query>"}
> 2. Ensure command_schema.py validates these structured outputs.
> 3. Ensure all tests in ai_engine/tests/ pass cleanly:
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
