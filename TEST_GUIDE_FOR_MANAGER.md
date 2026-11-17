# AI Desktop Companion — Test & Evaluation Guide for Manager

**Project:** AI Desktop Companion  
**Company:** JM Vertex Technologies  
**Module:** Windows Automation & Universal Voice/Text App Launching  
**Developer:** Logeshwaran D  
**Team Lead:** Vinay Vighnesh S  

---

## 1. Quick Start (One-Click)

1. Unzip the project folder on your laptop.
2. Double-click **`Launch-Companion.bat`**.
3. The companion will automatically start the Python universal automation engine and open the interactive desktop companion window with the animated Doraemon character.

---

## 2. Recommended Test Scenarios

### Test 1: Voice Commands (Microphone)
1. Click the **Microphone** button (or press `Ctrl + Space`).
2. Speak naturally:
   * *"Open Chrome"*
   * *"Launch Notepad"*
   * *"Can you open Calculator?"*
   * *"Open WhatsApp"*
3. **What happens:**
   * Doraemon listens with an active audio indicator.
   * Doraemon's animation changes to **Running** and glides across your desktop.
   * The application opens on your Windows screen.
   * Spoken audio confirms: *"[App Name] has been opened successfully."*

### Test 2: Text Commands (Chat Bar)
Type into the bottom command box and press **Enter**:
* `Word` (or `Open Microsoft Word`)
* `Excel`
* `Spotify`
* `Visual Studio Code`
* `Paint`

### Test 3: Ambiguous Application Name Handling
1. Type or speak: **`Open Microsoft`**
2. **What happens:** The system detects 30+ Microsoft apps (Word, Excel, PowerPoint, Access, Edge) and asks for clarification instead of guessing or launching randomly.

### Test 4: Security Policy & Anti-Injection Verification
1. Type: **`notepad && calc`** or **`test.bat`**
2. **What happens:** Blocked immediately with `ERR_TARGET_NOT_ALLOWLISTED`. Unrestricted shell commands and chaining are prevented.

---

## 3. Running Automated Test Suite (26 Tests)

To verify the test suite directly:

1. Open **Command Prompt (`cmd.exe`)** in the project folder.
2. Run:
```cmd
python -m unittest discover -s windows_automation/tests -v
```
All **26 tests** (unit tests, live Windows integration tests, and UWP/MSIX packaged app tests) will pass.

---

## 4. Minimum Prerequisites

* **OS:** Windows 10 or Windows 11 (64-bit or 32-bit).
* **Python:** 3.10+ installed (`python --version`).
* **Node.js:** 18+ installed (`node --version`).
