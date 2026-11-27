const { app, BrowserWindow, ipcMain, screen, Tray, Menu, nativeImage, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn } = require('child_process');
const { pathToFileURL } = require('url');
const { launchApp } = require('./appLauncher.cjs');
const { resolveAppTarget } = require('./shortcutDiscovery.cjs');
const { moveAvatarTo, returnHome, cancelActiveMovement } = require('./desktopMovement.cjs');
const { checkForUpdates, downloadAndApplyUpdate, getCurrentVersion, FALLBACK_MANUAL_URL } = require('./updater.cjs');


let dashboardWindow = null;
let avatarWindow = null;
let tray = null;
let pythonBackendProcess = null;
app.isQuitting = false;

function ensurePythonBackendRunning() {
  const req = http.get('http://127.0.0.1:8000/openapi.json', { timeout: 1200 }, (res) => {
    res.resume();
    console.log('[Backend] Python automation API already running on port 8000.');
  });
  req.on('error', () => {
    try {
      const repoRoot = path.join(__dirname, '..', '..');
      console.log('[Backend] Starting Python automation API on port 8000 from:', repoRoot);
      pythonBackendProcess = spawn('python', ['-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', '8000'], {
        cwd: repoRoot,
        windowsHide: true,
        stdio: 'ignore',
      });
      pythonBackendProcess.on('error', (err) => {
        console.warn('[Backend] Failed to spawn Python API:', err.message);
      });
    } catch (e) {
      console.warn('[Backend] Spawn error:', e.message);
    }
  });
}

// Ensure single instance of the application
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    // If user launches a second instance, bring windows to focus
    if (dashboardWindow && !dashboardWindow.isDestroyed()) {
      if (dashboardWindow.isMinimized()) dashboardWindow.restore();
      dashboardWindow.show();
      dashboardWindow.focus();
    }
    if (avatarWindow && !avatarWindow.isDestroyed() && avatarWindow.isVisible()) {
    }
  });
}

function getDevServerUrl() {
  if (process.env.VITE_DEV_SERVER_URL) {
    return process.env.VITE_DEV_SERVER_URL;
  }
  const urlFile = path.join(__dirname, '../dev-server-url.txt');
  if (fs.existsSync(urlFile)) {
    try {
      const savedUrl = fs.readFileSync(urlFile, 'utf8').trim();
      if (savedUrl) return savedUrl;
    } catch {
      // ignore
    }
  }
  return 'http://127.0.0.1:5173';
}

function loadWindow(win, viewName) {
  const distIndexPath = path.join(__dirname, '../dist/index.html');
  const isExplicitDev = Boolean(process.env.VITE_DEV_SERVER_URL) || process.argv.includes('--dev');
  const shouldUseProd = !isExplicitDev && fs.existsSync(distIndexPath);

  if (shouldUseProd) {
    const fileUrl = pathToFileURL(distIndexPath);
    fileUrl.searchParams.set('view', viewName);
    fileUrl.hash = viewName;
    return win.loadURL(fileUrl.href);
  }

  const baseUrl = getDevServerUrl();
  const targetUrl = new URL(baseUrl);
  targetUrl.searchParams.set('view', viewName);
  targetUrl.hash = viewName;

  return win.loadURL(targetUrl.href).catch((err) => {
    console.warn(`Initial load failed for ${targetUrl.href}, retrying in 500ms...`, err.message);
    setTimeout(() => {
      if (!win.isDestroyed()) {
        const retryBase = getDevServerUrl();
        const retryUrl = new URL(retryBase);
        retryUrl.searchParams.set('view', viewName);
        retryUrl.hash = viewName;
        win.loadURL(retryUrl.href).catch((retryErr) => {
          console.error(`Retry failed for ${retryUrl.href}:`, retryErr.message);
        });
      }
    }, 500);
  });
}

function createDashboardWindow() {
  if (dashboardWindow && !dashboardWindow.isDestroyed()) {
    dashboardWindow.show();
    dashboardWindow.focus();
    return;
  }

  dashboardWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'JM Vertex — AI Desktop Companion',
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  });

  loadWindow(dashboardWindow, 'dashboard');

  dashboardWindow.once('ready-to-show', () => {
    console.log('[Electron] Mission Control dashboard window ready and shown');
    dashboardWindow.show();
  });

  // When user closes dashboard window, hide it rather than quitting the entire application
  dashboardWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      dashboardWindow.hide();
    }
  });

  dashboardWindow.on('closed', () => {
    dashboardWindow = null;
  });
}

function createAvatarWindow() {
  if (avatarWindow && !avatarWindow.isDestroyed()) {
    avatarWindow.show();
    avatarWindow.focus();
    return;
  }

  const primaryDisplay = screen.getPrimaryDisplay();
  const workArea = primaryDisplay.workArea;

  const width = 240;
  const height = 300;
  // Position in bottom-right corner of work area with safe padding
  const x = Math.max(0, Math.round(workArea.x + workArea.width - width - 24));
  const y = Math.max(0, Math.round(workArea.y + workArea.height - height - 24));

  avatarWindow = new BrowserWindow({
    width,
    height,
    x,
    y,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    hasShadow: false,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: true,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  });

  // Keep floating window on top across all workspaces
  try {
    avatarWindow.setAlwaysOnTop(true, 'screen-saver');
  } catch {
    avatarWindow.setAlwaysOnTop(true);
  }

  loadWindow(avatarWindow, 'avatar');

    avatarWindow.once('ready-to-show', () => {
    console.log('[Electron] Floating companion avatar window ready and shown at', { x, y, width, height });
    avatarWindow.show();
    try {
      avatarWindow.setAlwaysOnTop(true, 'screen-saver');
    } catch {
      avatarWindow.setAlwaysOnTop(true);
    }
  });

  avatarWindow.webContents.on('console-message', (_e, level, message) => {
    console.log('[AvatarWindow:Console]', message);
  });

  avatarWindow.on('closed', () => {
    avatarWindow = null;
  });
}

function createTray() {
  try {
    const iconPath = path.join(__dirname, '../public/companion.webp.png');
    let trayIcon = nativeImage.createFromPath(iconPath);
    if (trayIcon.isEmpty()) {
      console.warn('Tray icon is empty, skipping tray creation');
      return;
    }
    trayIcon = trayIcon.resize({ width: 20, height: 20 });

    tray = new Tray(trayIcon);
    tray.setToolTip('JM Vertex — AI Desktop Companion');

    const updateTrayMenu = () => {
      const isAvatarVisible = avatarWindow && !avatarWindow.isDestroyed() && avatarWindow.isVisible();
      const isDashboardVisible = dashboardWindow && !dashboardWindow.isDestroyed() && dashboardWindow.isVisible();

      const contextMenu = Menu.buildFromTemplate([
        {
          label: isAvatarVisible ? 'Sleep Companion' : 'Show Companion (Wake)',
          click: () => {
            if (isAvatarVisible) {
              avatarWindow.hide();
            } else {
              if (!avatarWindow || avatarWindow.isDestroyed()) {
                createAvatarWindow();
              } else {
                avatarWindow.show();
                avatarWindow.setAlwaysOnTop(true, 'screen-saver');
              }
            }
            updateTrayMenu();
          },
        },
        {
          label: isDashboardVisible ? 'Bring Mission Control to Front' : 'Open Mission Control',
          click: () => {
            if (!dashboardWindow || dashboardWindow.isDestroyed()) {
              createDashboardWindow();
            } else {
              dashboardWindow.show();
              dashboardWindow.focus();
            }
            updateTrayMenu();
          },
        },
        { type: 'separator' },
        {
          label: 'Exit Application',
          click: () => {
            app.isQuitting = true;
            app.quit();
          },
        },
      ]);

      tray.setContextMenu(contextMenu);
    };

    updateTrayMenu();

    tray.on('double-click', () => {
      if (avatarWindow && !avatarWindow.isDestroyed() && avatarWindow.isVisible()) {
        if (!dashboardWindow || dashboardWindow.isDestroyed()) {
          createDashboardWindow();
        } else {
          dashboardWindow.show();
          dashboardWindow.focus();
        }
      } else {
        if (!avatarWindow || avatarWindow.isDestroyed()) {
                createAvatarWindow();
              } else {
          avatarWindow.show();
          avatarWindow.setAlwaysOnTop(true, 'screen-saver');
        }
      }
      updateTrayMenu();
    });
  } catch (error) {
    console.warn('Tray initialization skipped:', error.message);
  }
}

// IPC Handlers
// -- App Launcher IPC Handler --------------------------------------------------
// Accepts only an app identifier string against an explicit allowlist.
// Never executes arbitrary shell commands from the renderer.
ipcMain.handle('companion:launch-app', async (_event, appId, options) => {
  console.log('[Electron] companion:launch-app requested for:', appId, options);
  try {
    const result = await launchApp(appId, options);
    console.log('[Electron] companion:launch-app result:', result);
    return result;
  } catch (err) {
    console.error('[Electron] companion:launch-app unexpected error:', err);
    return {
      success: false,
      verified: false,
      displayName: appId,
      mode: 'real',
      error: 'Unexpected launcher error: ' + err.message,
    };
  }
});
let executionMode = 'real'; // 'real' | 'mock'

ipcMain.handle('companion:set-execution-mode', (_event, mode) => {
  executionMode = mode === 'mock' ? 'mock' : 'real';
  console.log('[Electron] Execution mode set to:', executionMode);
  return executionMode;
});

ipcMain.handle('companion:get-execution-mode', () => {
  return executionMode;
});

ipcMain.handle('companion:cancel-movement', () => {
  console.log('[Electron] Movement cancelled by user request');
  cancelActiveMovement();
  if (avatarWindow && !avatarWindow.isDestroyed()) {
    avatarWindow.webContents.send('companion:sync-state', {
      avatarState: 'Error',
      taskState: 'cancelled',
      isMoving: false,
    });
  }
  return true;
});

ipcMain.handle('companion:return-home', async () => {
  if (avatarWindow && !avatarWindow.isDestroyed()) {
    return await returnHome(avatarWindow);
  }
  return false;
});

// -- Auto-Updater IPC Handlers -------------------------------------------------
ipcMain.handle('companion:check-updates', async () => {
  console.log('[Electron] Checking for updates...');
  try {
    return await checkForUpdates();
  } catch (err) {
    return {
      updateAvailable: false,
      currentVersion: getCurrentVersion(),
      error: err.message,
      manualUrl: FALLBACK_MANUAL_URL,
    };
  }
});

ipcMain.handle('companion:apply-update', async (_event, updateInfo) => {
  console.log('[Electron] Applying update:', updateInfo);
  try {
    const result = await downloadAndApplyUpdate(updateInfo);
    if (result.success) {
      // Broadcast update completion
      if (dashboardWindow && !dashboardWindow.isDestroyed()) {
        dashboardWindow.webContents.send('companion:update-completed', result);
      }
      if (avatarWindow && !avatarWindow.isDestroyed()) {
        avatarWindow.webContents.send('companion:update-completed', result);
      }
    }
    return result;
  } catch (err) {
    return {
      success: false,
      error: err.message,
      manualUrl: FALLBACK_MANUAL_URL,
    };
  }
});

ipcMain.handle('companion:open-external', async (_event, url) => {
  const target = url || FALLBACK_MANUAL_URL;
  console.log('[Electron] Opening external URL in browser:', target);
  shell.openExternal(target);
  return true;
});

ipcMain.handle('companion:get-current-version', () => {
  return getCurrentVersion();
});

ipcMain.handle('companion:relaunch-app', () => {
  console.log('[Electron] Relaunching application to apply updates...');
  if (pythonBackendProcess && !pythonBackendProcess.killed) {
    try { pythonBackendProcess.kill(); } catch {}
  }
  app.relaunch();
  app.exit(0);
});

// -- Physical Desktop Movement & Launch Pipeline ---------------------------------
ipcMain.handle('companion:start-desktop-task', async (_event, { appId, displayName, query }) => {
  console.log(`[Electron] Starting desktop task for "${appId}" (${displayName}) query="${query || ''}" in ${executionMode} mode`);

  // Step 1: Discovered Desktop Shortcut or Calculated Destination
  const targetInfo = resolveAppTarget(appId);
  console.log('[Electron] Discovered target info:', targetInfo);

  if (dashboardWindow && !dashboardWindow.isDestroyed()) {
    dashboardWindow.webContents.send('companion:task-progress', {
      phase: 'planning',
      appId,
      displayName,
      targetInfo,
      executionMode,
    });
  }

  // Step 2: Physical Movement across Windows Desktop
  let moveResult = { completed: true, cancelled: false };

  if (avatarWindow && !avatarWindow.isDestroyed()) {
    // If chatbox is open, collapse back to compact avatar window (240x300) before travelling
    const [currW, currH] = avatarWindow.getSize();
    if (currW > 240 || currH > 300) {
      const [currX, currY] = avatarWindow.getPosition();
      avatarWindow.setBounds({
        x: currX,
        y: Math.round(currY + (currH - 300)),
        width: 240,
        height: 300,
      });
      avatarWindow.webContents.send('companion:sync-state', {
        chatboxOpen: false,
      });
    }

    avatarWindow.show();
    avatarWindow.webContents.send('companion:sync-state', {
      avatarState: 'Working',
      taskState: 'launching',
      isMoving: true,
      chatboxOpen: false,
    });

    moveResult = await moveAvatarTo(
      avatarWindow,
      targetInfo.destination.x,
      targetInfo.destination.y,
      {
        onStep: (stepData) => {
          if (dashboardWindow && !dashboardWindow.isDestroyed()) {
            dashboardWindow.webContents.send('companion:movement-progress', stepData);
          }
        },
      }
    );
  }

  if (moveResult.cancelled) {
    return {
      success: false,
      cancelled: true,
      taskState: 'cancelled',
      displayName: displayName || appId,
      executionMode,
      error: 'Movement cancelled by user',
    };
  }

  // Step 3: Launch Application
  let launchResult;
  if (executionMode === 'mock') {
    await new Promise((r) => setTimeout(r, 800));
    launchResult = {
      success: true,
      verified: false,
      displayName: displayName || appId,
      mode: 'mock',
      mockSimulated: true,
      message: `[MOCK MODE] Simulated launch of ${displayName || appId}. No real Windows process was started.`,
    };
  } else {
    launchResult = await launchApp(appId, { query });
  }

  // Step 4: Verification and Celebration
  const finalState = launchResult.success ? 'success' : 'failed';

  if (avatarWindow && !avatarWindow.isDestroyed()) {
    avatarWindow.webContents.send('companion:sync-state', {
      avatarState: launchResult.success ? 'Success' : 'Error',
      taskState: finalState,
      isMoving: false,
    });
  }

  if (dashboardWindow && !dashboardWindow.isDestroyed()) {
    dashboardWindow.webContents.send('companion:task-progress', {
      phase: finalState,
      appId,
      displayName,
      launchResult,
      executionMode,
    });
  }

  return {
    ...launchResult,
    taskState: finalState,
    targetInfo,
    executionMode,
  };
});

ipcMain.handle('companion:open-dashboard', () => {
  if (!dashboardWindow || dashboardWindow.isDestroyed()) {
    createDashboardWindow();
  } else {
    if (dashboardWindow.isMinimized()) dashboardWindow.restore();
    dashboardWindow.show();
    dashboardWindow.focus();
  }
  return true;
});

ipcMain.handle('companion:close-dashboard', () => {
  if (dashboardWindow && !dashboardWindow.isDestroyed()) {
    dashboardWindow.hide();
  }
  return true;
});

ipcMain.handle('companion:sleep-avatar', () => {
  if (avatarWindow && !avatarWindow.isDestroyed()) {
    avatarWindow.hide();
  }
  return true;
});

ipcMain.handle('companion:wake-avatar', () => {
  if (!avatarWindow || avatarWindow.isDestroyed()) {
    createAvatarWindow();
  } else {
    avatarWindow.show();
    try {
      avatarWindow.setAlwaysOnTop(true, 'screen-saver');
    } catch {
      avatarWindow.setAlwaysOnTop(true);
    }
  }
  return true;
});

ipcMain.handle('companion:set-chatbox-open', (_event, isOpen) => {
  if (!avatarWindow || avatarWindow.isDestroyed()) return false;
  const [currX, currY] = avatarWindow.getPosition();
  const [_currW, currH] = avatarWindow.getSize();
  const primaryDisplay = screen.getDisplayNearestPoint({ x: currX, y: currY });
  const workArea = primaryDisplay.workArea;

  if (isOpen) {
    const targetW = 660;
    const targetH = 540;
    // Doraemon is positioned on the LEFT side of the expanded window.
    // Anchor Doraemon's X coordinate stably at currX (the chatbox opens to his right).
    let targetX = currX;
    if (targetX + targetW > workArea.x + workArea.width) {
      targetX = workArea.x + workArea.width - targetW;
    }
    targetX = Math.max(workArea.x, targetX);

    // Anchor vertically to bottom so Doraemon remains grounded on the desktop
    let targetY = currY - (targetH - currH);
    targetY = Math.max(workArea.y, Math.min(targetY, workArea.y + workArea.height - targetH));
    avatarWindow.setBounds({ x: targetX, y: targetY, width: targetW, height: targetH });
  } else {
    const targetW = 240;
    const targetH = 300;
    // Doraemon was on the LEFT side of the expanded window, so his X was currX.
    let targetX = currX;
    targetX = Math.max(workArea.x, Math.min(targetX, workArea.x + workArea.width - targetW));

    let targetY = currY + (currH - targetH);
    targetY = Math.max(workArea.y, Math.min(targetY, workArea.y + workArea.height - targetH));
    avatarWindow.setBounds({ x: targetX, y: targetY, width: targetW, height: targetH });
  }
  return true;
});

ipcMain.handle('companion:move-avatar', (_event, { deltaX, deltaY }) => {
  if (avatarWindow && !avatarWindow.isDestroyed()) {
    const [currX, currY] = avatarWindow.getPosition();
    avatarWindow.setPosition(Math.round(currX + (deltaX || 0)), Math.round(currY + (deltaY || 0)));
  }
  return true;
});

ipcMain.handle('companion:quit-app', () => {
  app.isQuitting = true;
  app.quit();
});

ipcMain.handle('companion:trigger-voice-typing', async () => {
  const { exec } = require('child_process');
  const psFile = path.join(__dirname, 'triggerVoiceTyping.ps1');
  return new Promise((resolve) => {
    exec(`powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "${psFile}"`, (err, stdout) => {
      if (err) {
        console.warn('[Electron] Trigger voice typing error:', err);
        resolve(false);
      } else {
        console.log('[Electron] Triggered Windows Voice Typing (Win+H):', (stdout || '').trim());
        resolve(true);
      }
    });
  });
});

ipcMain.handle('companion:sync-state', (_event, data) => {
  // Broadcast state to all windows
  if (dashboardWindow && !dashboardWindow.isDestroyed()) {
    dashboardWindow.webContents.send('companion:sync-state', data);
  }
  if (avatarWindow && !avatarWindow.isDestroyed()) {
    avatarWindow.webContents.send('companion:sync-state', data);
  }
  return true;
});

app.whenReady().then(() => {
  console.log('[Electron] Application ready. Initializing Dashboard, Avatar, and System Tray...');
  ensurePythonBackendRunning();
  createDashboardWindow();
  createAvatarWindow();
  createTray();
  console.log('[Electron] Started with Mission Control Dashboard and floating Doraemon companion.');

  // Automatic update check 4 seconds after launch
  setTimeout(async () => {
    try {
      const updateResult = await checkForUpdates();
      if (updateResult && updateResult.updateAvailable) {
        console.log('[Updater] Update available notice: v' + updateResult.remoteVersion);
        if (dashboardWindow && !dashboardWindow.isDestroyed()) {
          dashboardWindow.webContents.send('companion:update-available', updateResult);
        }
        if (avatarWindow && !avatarWindow.isDestroyed()) {
          avatarWindow.webContents.send('companion:update-available', updateResult);
        }
      }
    } catch (err) {
      console.warn('[Updater] Silent startup update check notice:', err.message);
    }
  }, 4000);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createDashboardWindow();
    }
  });
});

app.on('before-quit', () => {
  app.isQuitting = true;
});

app.on('before-quit', () => {
  if (pythonBackendProcess && !pythonBackendProcess.killed) {
    try {
      pythonBackendProcess.kill();
    } catch {}
  }
});

app.on('window-all-closed', () => {
  // If app is not explicitly quitting, keep running in tray if tray exists
  if (app.isQuitting || !tray) {
    app.quit();
  }
});
