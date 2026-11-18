# JM VERTEX — AI Desktop Companion 🤖✨
## 📋 Tester Quickstart & Verification Guide (v1.0.0 Test Release)

Thank you for testing the **JM Vertex AI Desktop Companion** on your laptop!

---

### 💻 System Prerequisites
Before running, make sure your laptop has:
* **Operating System**: Windows 10 or Windows 11 (64-bit)
* **Python**: Python 3.10 or 3.11 installed (with `python` on PATH)
* **Node.js**: Node.js 18+ installed (with `npm` on PATH)
* **Microphone**: Laptop built-in microphone for voice commands

---

### 🚀 Method 1: 1-Click Launch (Recommended)
Simply double-click the included batch launcher at the root folder:
```bat
Launch-Companion.bat
```
This script will automatically:
1. Verify Python & Node.js on your laptop.
2. Start the Python FastAPI Universal Automation Backend on `http://127.0.0.1:8000`.
3. Check and install frontend dependencies if needed.
4. Launch the transparent floating companion avatar on your screen.

---

### 🚀 Method 2: GUI Setup Wizard (.exe)
If you prefer an installation wizard that creates a Desktop shortcut:
1. Double-click **`JM-Vertex-AI-Companion-Setup.exe`** (in `installer/` or `downloads/`).
2. Click **"INSTALL FOR THIS LAPTOP"** — it validates your hardware profile and creates a 1-click shortcut.

---

### 🧪 What to Test on Your Laptop:

#### 1. Animated Avatar Presence & Taskbar Docking
* The floating Doraemon avatar should appear on your screen with smooth 8-frame walking animations.
* It docks neatly right above the Windows taskbar.
* You should be able to click icons or windows underneath it (transparent click-through).

#### 2. Smart Multi-Path Application Launch
Test these voice or text commands:
* **"Open YouTube"** &rarr; Since YouTube desktop app usually isn't on Windows, the companion should automatically detect Google Chrome/Edge, open `https://youtube.com`, and verify the process in Windows `tasklist`.
* **"Open Notepad"** &rarr; Launches Windows Notepad native executable and confirms truthful process creation.
* **"Launch Spotify"** &rarr; Launches native Spotify if installed, or falls back to Spotify Web Player.
* **"Open Calculator"** / **"Open File Explorer"** &rarr; Launches Windows native system utilities.

#### 3. Interactive CLI Testing
To test application discovery and Win32 policy validation directly in your terminal:
```powershell
python run_local.py
```
* Type `scan` to see all 32/64-bit and UWP applications detected on your laptop.
* Type `Open Notepad` or `calc` to test controlled safe execution.
* Type `test` to run integration tests.

---

### ⚠️ Troubleshooting
* **Backend didn't start?** Ensure port 8000 is free (`netstat -ano | findstr :8000`).
* **Microphone not picking up?** Check Windows Settings &rarr; Privacy & Security &rarr; Microphone &rarr; "Allow apps to access your microphone".

---
*JM Vertex Technologies — Engineering Team: Logeshwaran D, Madhan M, Hariram K S, Booviha M.*
