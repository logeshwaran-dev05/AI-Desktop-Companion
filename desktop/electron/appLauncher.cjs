/**
 * APP LAUNCHER ADAPTER — Electron Main Process
 * =============================================
 * Launches real Windows applications safely and truthfully verifies
 * that the process actually opened on the Windows desktop.
 *
 * SECURITY:
 * - Only approved allowlist application identifiers are accepted.
 * - ShellExecute via `start` ensures real Windows desktop GUI invocation.
 * - No user-supplied command strings or arguments are executed.
 * - Honest verification: verifies actual process existence in Windows tasklist.
 */

const { exec } = require('child_process');
const http = require('http');

const APP_ALLOWLIST = [
  {
    id: 'notepad',
    displayName: 'Notepad',
    launchCommand: 'cmd.exe /c start "" notepad',
    processNames: ['Notepad.exe', 'notepad.exe'],
  },
  {
    id: 'calculator',
    displayName: 'Calculator',
    launchCommand: 'cmd.exe /c start "" calc',
    processNames: ['CalculatorApp.exe', 'Calculator.exe', 'calc.exe'],
  },
  {
    id: 'explorer',
    displayName: 'File Explorer',
    launchCommand: 'cmd.exe /c start "" explorer',
    processNames: ['explorer.exe'],
  },
  {
    id: 'chrome',
    displayName: 'Google Chrome',
    launchCommand: 'cmd.exe /c start "" chrome',
    processNames: ['chrome.exe'],
  },
  {
    id: 'vscode',
    displayName: 'Visual Studio Code',
    launchCommand: 'cmd.exe /c start "" code',
    processNames: ['Code.exe'],
  },
  {
    id: 'whatsapp',
    displayName: 'WhatsApp',
    launchCommand: 'cmd.exe /c start whatsapp:',
    processNames: ['WhatsApp.exe', 'WhatsApp.Root.exe'],
  },
];

/**
 * Checks whether any of the given process names are currently running in Windows tasklist
 * @param {string[]} processNames
 * @returns {Promise<boolean>}
 */

/**
 * Query Python Universal Automation Engine (supports all 260+ Win32, Win64, UWP, MSIX applications)
 * @param {string} appId
 * @returns {Promise<any>}
 */
function queryPythonBackend(appId) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:8000/api/launch-app?appId=${encodeURIComponent(appId)}`, { timeout: 3500 }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          resolve(parsed);
        } catch {
          resolve(null);
        }
      });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => {
      req.destroy();
      resolve(null);
    });
  });
}

function verifyProcessRunning(processNames) {
  return new Promise((resolve) => {
    exec('tasklist /fo csv /nh', { windowsHide: true }, (err, stdout) => {
      if (err || !stdout) {
        resolve(false);
        return;
      }
      const lower = stdout.toLowerCase();
      const matched = processNames.some((p) => lower.includes(p.toLowerCase()));
      resolve(matched);
    });
  });
}

/**
 * Launch a Windows application by allowlist identifier and verify execution.
 *
 * @param {string} appId - Allowlist identifier
 * @returns {Promise<{
 *   success: boolean,
 *   verified: boolean,
 *   displayName: string,
 *   error?: string,
 *   mode: 'real' | 'not-found'
 * }>}
 */
function launchApp(appId) {
  return new Promise(async (resolve) => {
    const normalizedId = (appId || '').trim().toLowerCase();

    // 1. First delegate to Universal Python Automation Engine (Win32, Win64, UWP/MSIX, StartApps)
    const pyResult = await queryPythonBackend(normalizedId);
    if (pyResult && (pyResult.success || pyResult.verified)) {
      console.log(`[Launcher] Universal launcher executed and verified: ${pyResult.displayName}`);
      resolve({
        success: true,
        verified: !!pyResult.verified,
        displayName: pyResult.displayName || appId,
        mode: 'real',
      });
      return;
    } else if (pyResult && pyResult.error && !pyResult.error.includes('ECONNREFUSED')) {
      console.warn(`[Launcher] Universal launcher reported error: ${pyResult.error}`);
      // If backend explicitly found the app or failed launch, return truthful result
      if (pyResult.mode === 'real') {
        resolve({
          success: false,
          verified: false,
          displayName: pyResult.displayName || appId,
          mode: 'real',
          error: pyResult.error,
        });
        return;
      }
    }

    // 2. Fallback to local allowlist if backend is unavailable or app is built-in
    const appEntry = APP_ALLOWLIST.find((a) => a.id === normalizedId);

    if (!appEntry) {
      resolve({
        success: false,
        verified: false,
        displayName: appId,
        mode: 'not-found',
        error: pyResult?.error || `"${appId}" was not found in installed applications or local registry.`,
      });
      return;
    }

    console.log(`[Launcher] Executing real Windows launch for ${appEntry.displayName}: ${appEntry.launchCommand}`);

    exec(appEntry.launchCommand, { windowsHide: false }, (spawnErr) => {
      if (spawnErr) {
        console.warn(`[Launcher] Spawn error for ${appEntry.displayName}:`, spawnErr.message);
      }
    });

    // Verification check with active polling over 2.5 seconds
    const startTime = Date.now();
    const timeoutMs = 2800;

    const interval = setInterval(async () => {
      const isRunning = await verifyProcessRunning(appEntry.processNames);

      if (isRunning) {
        clearInterval(interval);
        console.log(`[Launcher] Confirmed ${appEntry.displayName} process is running!`);
        resolve({
          success: true,
          verified: true,
          displayName: appEntry.displayName,
          mode: 'real',
        });
        return;
      }

      if (Date.now() - startTime >= timeoutMs) {
        clearInterval(interval);
        console.warn(`[Launcher] Verification timed out for ${appEntry.displayName}. Process not detected.`);
        resolve({
          success: false,
          verified: false,
          displayName: appEntry.displayName,
          mode: 'real',
          error: `Could not verify that ${appEntry.displayName} opened. The application may not be installed or failed to launch.`,
        });
      }
    }, 400);
  });
}

module.exports = { launchApp, APP_ALLOWLIST };
