"""
Generate Sprint Task Allocation PDF for the team in Downloads folder.
"""

import os
import subprocess
import tempfile

html_content = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>JM Vertex AI Desktop Companion — Sprint Task Allocation</title>
<style>
  @page {
    size: A4;
    margin: 12mm 15mm 12mm 15mm;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    line-height: 1.45;
    font-size: 12px;
    background: #fff;
    margin: 0;
    padding: 0;
  }
  .header {
    border-bottom: 2px solid #00E676;
    padding-bottom: 10px;
    margin-bottom: 14px;
  }
  .company {
    font-size: 10px;
    font-weight: 700;
    color: #00875A;
    letter-spacing: 1.5px;
    text-transform: uppercase;
  }
  h1 {
    font-size: 20px;
    margin: 3px 0 5px 0;
    color: #0f172a;
  }
  .subtitle {
    font-size: 12px;
    color: #64748b;
  }
  .meta-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 14px;
    display: table;
    width: 100%;
    box-sizing: border-box;
  }
  .meta-item {
    display: table-cell;
    font-size: 11px;
  }
  .meta-label {
    font-weight: 600;
    color: #475569;
  }
  .meta-val a {
    color: #0284c7;
    text-decoration: none;
  }
  .section-title {
    font-size: 13px;
    font-weight: 700;
    color: #0f172a;
    border-left: 4px solid #00E676;
    padding-left: 8px;
    margin: 14px 0 8px 0;
  }
  .role-card {
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 12px;
    background: #ffffff;
    page-break-inside: avoid;
  }
  .role-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }
  .member-name {
    font-size: 14px;
    font-weight: 700;
    color: #0f172a;
  }
  .badge {
    display: inline-block;
    padding: 2px 7px;
    font-size: 10px;
    font-weight: 700;
    border-radius: 4px;
    text-transform: uppercase;
  }
  .badge-backend { background: #e0f2fe; color: #0369a1; }
  .badge-frontend { background: #fef3c7; color: #b45309; }
  .badge-ml { background: #f3e8ff; color: #7e22ce; }
  .files-tag {
    font-size: 10.5px;
    color: #64748b;
    margin-bottom: 6px;
  }
  ul {
    margin: 4px 0 8px 16px;
    padding: 0;
  }
  li {
    margin-bottom: 3px;
  }
  .prompt-box {
    background: #0f172a;
    color: #f1f5f9;
    border-radius: 5px;
    padding: 10px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 10px;
    line-height: 1.4;
    white-space: pre-wrap;
    word-break: break-word;
    margin-top: 6px;
  }
  .prompt-title {
    font-size: 10px;
    font-weight: 700;
    color: #38bdf8;
    text-transform: uppercase;
    margin-bottom: 3px;
  }
</style>
</head>
<body>

<div class="header">
  <div class="company">JM VERTEX TECHNOLOGIES — AI COMPANION PLATFORM</div>
  <h1>Sprint Task Allocation &amp; Technical Implementation Guide</h1>
  <div class="subtitle">Autonomous Multi-Step Execution, Google Chrome Profile Bypassing &amp; GUI Action Primitives</div>
</div>

<div class="meta-box">
  <div class="meta-item"><span class="meta-label">Date:</span> November 21, 2026</div>
  <div class="meta-item"><span class="meta-label">Active Branch:</span> <code>main</code></div>
  <div class="meta-item"><span class="meta-label">GitHub Repo:</span> <a href="https://github.com/logeshwaran-dev05/AI-Desktop-Companion">logeshwaran-dev05/AI-Desktop-Companion</a></div>
  <div class="meta-item"><span class="meta-label">Live Site:</span> <a href="https://logeshwaran-dev05.github.io/AI-Desktop-Companion/">GitHub Pages Live</a></div>
</div>

<div class="section-title">Executive Summary &amp; Problem Statement</div>
<p style="margin: 0 0 10px 0;">
We are upgrading the AI Companion to autonomously execute multi-step chained instructions (e.g. <i>'Open ChatGPT, ask X, and paste in Notepad'</i> or <i>'Open YouTube and play 2nd video for lofi hip hop'</i>). Additionally, laptops with multiple Chrome accounts (e.g. Logesh, LOKI, Aimtech) were previously halting at the <b>'Who is using Chrome?' Profile Picker dialog</b>. We have pushed <code>windows_automation/browser_profiles.py</code> to main to discover profiles from <code>Local State</code> and allow direct launching with <code>--profile-directory</code> to bypass the dialog completely.
</p>

<!-- 1. LALITH PRABHU -->
<div class="role-card">
  <div class="role-header">
    <span class="member-name">1. Lalith Prabhu</span>
    <span class="badge badge-backend">Backend Developer (Automation Execution &amp; OS Primitives)</span>
  </div>
  <div class="files-tag"><b>Target Files:</b> <code>windows_automation/executor.py</code>, <code>windows_automation/browser_profiles.py</code></div>
  <b>Tasks &amp; Responsibilities:</b>
  <ul>
    <li><b>Chrome Profile Bypass:</b> Integrate <code>build_chrome_launch_args</code> into <code>WindowsAutomationExecutor.execute()</code> so Chrome launches directly with <code>--profile-directory="&lt;dir&gt;"</code>, bypassing the profile picker screen.</li>
    <li><b>GUI Action Primitives:</b> Implement execution handlers for <code>type_text(text, enter)</code>, <code>clipboard_copy()</code> (Ctrl+C into pyperclip), <code>clipboard_paste(app)</code> (Ctrl+V into target app), and <code>click_youtube_result(ordinal_index)</code>.</li>
    <li><b>Verification:</b> Maintain passing state on all 22 <code>windows_automation</code> tests.</li>
  </ul>
  <div class="prompt-title">Ready-to-Send Prompt for Lalith Prabhu:</div>
  <div class="prompt-box">Hi Lalith, welcome! Your backend task is the Windows automation execution layer.
Repo: https://github.com/logeshwaran-dev05/AI-Desktop-Companion (Branch: main)
1. In windows_automation/executor.py, wire build_chrome_launch_args() from windows_automation/browser_profiles.py so Chrome launches with --profile-directory="Profile 2" (bypassing the Chrome profile picker).
2. Implement GUI primitives:
   - type_text(text: str, press_enter: bool = True) -> simulates typing into active window
   - clipboard_copy() -> captures text via pyperclip
   - clipboard_paste(target_app: str) -> focuses target window and triggers Ctrl+V
   - click_youtube_result(ordinal_index: int) -> clicks the N-th video in search results
3. Run test suite: python -m unittest discover -s windows_automation/tests -p "test_*.py"</div>
</div>

<!-- 2. HARIRAM -->
<div class="role-card">
  <div class="role-header">
    <span class="member-name">2. Hariram</span>
    <span class="badge badge-backend">Backend Developer (Orchestration Pipeline &amp; REST APIs)</span>
  </div>
  <div class="files-tag"><b>Target Files:</b> <code>api/orchestrator.py</code>, <code>api/main.py</code>, <code>api/schemas.py</code></div>
  <b>Tasks &amp; Responsibilities:</b>
  <ul>
    <li><b>Sequential Orchestration Loop:</b> Update <code>TaskOrchestrator.execute_task()</code> to execute a chain of <code>PlanStep</code> items sequentially, piping data (e.g. copied clipboard text) across steps.</li>
    <li><b>REST Endpoints:</b> Add <code>GET /api/browser/profiles</code> returning detected Chrome profiles so Madhan's frontend can render the dropdown.</li>
    <li><b>Verification:</b> Maintain passing state on all 83 <code>api/tests</code>.</li>
  </ul>
  <div class="prompt-title">Ready-to-Send Prompt for Hariram:</div>
  <div class="prompt-box">Hi Hariram, your backend task is the Task Orchestrator &amp; REST API layer.
Repo: https://github.com/logeshwaran-dev05/AI-Desktop-Companion (Branch: main)
1. Add GET /api/browser/profiles in api/main.py that calls get_browser_profiles("chrome") from windows_automation.browser_profiles.
2. In api/orchestrator.py, update TaskOrchestrator to loop through multi-step plans (List[PlanStep]), passing step context (like copied clipboard text) into downstream steps.
3. Handle step failure diagnostics gracefully.
4. Run test suite: python -m unittest discover -s api/tests -p "test_*.py"</div>
</div>

<!-- 3. MADHAN -->
<div class="role-card">
  <div class="role-header">
    <span class="member-name">3. Madhan</span>
    <span class="badge badge-frontend">Frontend Developer (React / Electron / Desktop UI)</span>
  </div>
  <div class="files-tag"><b>Target Files:</b> <code>desktop/src/App.tsx</code>, <code>desktop/electron/main.cjs</code></div>
  <b>Tasks &amp; Responsibilities:</b>
  <ul>
    <li><b>Profile Clarification UI:</b> When backend returns <code>status: 'clarification_required'</code>, render clickable option pills in chat (<code>[👤 Logesh]</code>, <code>[👤 LOKI]</code>, <code>[👤 Aimtech]</code>).</li>
    <li><b>Default Profile Dropdown in Settings:</b> Fetch profiles from Hariram's <code>GET /api/browser/profiles</code> and let users save a default Chrome profile.</li>
    <li><b>Multi-Step Progress Feedback:</b> Show real-time progress toasts (e.g. <i>'Step 1/3: Opening YouTube...'</i>).</li>
  </ul>
  <div class="prompt-title">Ready-to-Send Prompt for Madhan:</div>
  <div class="prompt-box">Hi Madhan, your frontend task is the Profile Clarification UI &amp; Settings selector.
Repo: https://github.com/logeshwaran-dev05/AI-Desktop-Companion (Branch: main)
1. In desktop/src/App.tsx, when backend returns clarification_required with profile options, render interactive choice chips in the chat feed ([👤 Logesh] [👤 LOKI] [👤 Aimtech]). Clicking one resumes the plan.
2. Under Settings -> General Settings, add a 'Default Chrome Profile' dropdown populated via GET http://127.0.0.1:8000/api/browser/profiles. Persist the chosen profile in localStorage.
3. Show step-by-step toast progress during multi-step runs.
4. Verify build: npm --prefix desktop run build</div>
</div>

<!-- 4. BOOVIHA -->
<div class="role-card">
  <div class="role-header">
    <span class="member-name">4. Booviha</span>
    <span class="badge badge-ml">ML &amp; NLP Engineer (Task Planner &amp; Entity Extractor)</span>
  </div>
  <div class="files-tag"><b>Target Files:</b> <code>ai_engine/planner/task_planner.py</code>, <code>ai_engine/nlp/entity_extractor.py</code></div>
  <b>Tasks &amp; Responsibilities:</b>
  <ul>
    <li><b>Multi-Step Decomposition:</b> Break user instructions into an ordered list of <code>PlanStep</code> objects.</li>
    <li><b>Ordinal &amp; Query Extraction:</b> Extract '1st' -> 0, '2nd' -> 1, and search queries / prompts.</li>
    <li><b>Profile Mention Extraction:</b> Extract profile mentions (e.g. 'on LOKI profile') and resolve using <code>browser_profiles.resolve_profile_directory</code>.</li>
  </ul>
  <div class="prompt-title">Ready-to-Send Prompt for Booviha:</div>
  <div class="prompt-box">Hi Booviha, your ML task is the Multi-Step Task Planner &amp; Entity Extractor.
Repo: https://github.com/logeshwaran-dev05/AI-Desktop-Companion (Branch: main)
1. Update ai_engine/planner/task_planner.py to output chained PlanSteps (e.g. navigate_url -> type_text -> wait -> clipboard_copy -> launch_app -> clipboard_paste).
2. In entity_extractor.py, extract ordinals ('1st' -> 0, '2nd' -> 1) and search queries / prompt text.
3. Match profile mentions ('on LOKI') using windows_automation.browser_profiles.resolve_profile_directory().
4. Run test suite: python -m unittest discover -s ai_engine/tests -p "test_*.py"</div>
</div>

</body>
</html>
"""

def generate_pdf():
    temp_dir = tempfile.gettempdir()
    temp_html = os.path.join(temp_dir, "task_allocation.html")
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    downloads_dir = os.path.expanduser("~/Downloads")
    output_pdf = os.path.join(downloads_dir, "JM_Vertex_Sprint_Task_Allocation.pdf")

    chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    cmd = [
        chrome_exe,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={output_pdf}",
        temp_html
    ]

    subprocess.run(cmd, check=True)
    size_bytes = os.path.getsize(output_pdf)
    print(f"SUCCESS: PDF created at: {output_pdf}")
    print(f"File size: {size_bytes} bytes (~{round(size_bytes / 1024, 1)} KB)")

if __name__ == "__main__":
    generate_pdf()
