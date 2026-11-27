const { app, BrowserWindow, ipcMain, screen, Tray, Menu, nativeImage, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn } = require('child_process');
const { pathToFileURL } = require('url');
const { launchApp, APP_REGISTRY, waitForProcess } = require('./appLauncher.cjs');
const {
  resolveDestination,
  getStartButtonCoordinates,
  openStartAndGetSearchBox,
  searchAndGetResultCoordinates,
  closeStartMenu,
  getCanonicalProcessNames,
} = require('./destinationResolver.cjs');
const { moveAvatarTo, returnHome, cancelActiveMovement } = require('./desktopMovement.cjs');
const { AVATAR_CONFIG } = require('./avatarConfig.cjs');
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

  const width = AVATAR_CONFIG.windowWidth;
  const height = AVATAR_CONFIG.windowHeight;
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

ipcMain.handle('companion:cancel-task', () => {
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

ipcMain.handle('companion:cancel-active-movement', () => {
  cancelActiveMovement();
  return true;
});

ipcMain.handle('companion:return-home', async () => {
  if (avatarWindow && !avatarWindow.isDestroyed()) {
    return await returnHome(avatarWindow);
  }
  return false;
});

ipcMain.handle('companion:resolve-destination', async (_event, query) => {
  const primaryDisplay = screen.getPrimaryDisplay();
  return await resolveDestination(query, {
    workArea: primaryDisplay.workArea,
    scaleFactor: primaryDisplay.scaleFactor || 1.0,
  });
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
  app.relaunch();
  app.exit(0);
});

// -- Destination-Based Desktop Movement & Launch Pipeline ---------------------
ipcMain.handle('companion:start-desktop-task', async (_event, payload = {}) => {
  const { appId, displayName, rawCommand, pathChoice, targetKind, query, actionType } = payload;
  const targetQuery = rawCommand || displayName || appId || '';

  // Extract effective query and actionType if not explicitly supplied
  let effectiveQuery = query || '';
  let effectiveActionType = actionType || 'open';
  if (!effectiveQuery) {
    const playMatch = targetQuery.match(/\bplay\s+(.+?)(?:\s+on\s+(?:youtube|spotify)|\s*$)/i);
    const searchMatch = targetQuery.match(/\bsearch\s+(.+?)(?:\s+on\s+(?:youtube|spotify)|\s*$)/i);
    if (playMatch) {
      effectiveQuery = playMatch[1].replace(/\b(?:on\s+youtube|on\s+spotify)\b/i, '').trim();
      effectiveActionType = 'play';
    } else if (searchMatch) {
      effectiveQuery = searchMatch[1].replace(/\b(?:on\s+youtube|on\s+spotify)\b/i, '').trim();
      effectiveActionType = 'search';
    }
  }

  console.log(`[Electron] Starting destination-based task for "${targetQuery}" query="${effectiveQuery}" actionType="${effectiveActionType}" in ${executionMode} mode (kind: ${targetKind || 'auto'})`);

  const primaryDisplay = screen.getPrimaryDisplay();
  const workArea = primaryDisplay.workArea;
  const scaleFactor = primaryDisplay.scaleFactor || 1.0;

  // Broadcast real-time progress message to both Avatar and Dashboard
  const broadcastProgress = (progressData) => {
    if (dashboardWindow && !dashboardWindow.isDestroyed()) {
      dashboardWindow.webContents.send('companion:task-progress', progressData);
    }
    if (avatarWindow && !avatarWindow.isDestroyed()) {
      avatarWindow.webContents.send('companion:task-progress', progressData);
    }
  };

  const isExplorerApp = Boolean(targetQuery.match(/\b(?:file\s+explorer|explorer|my\s+computer|file\s+manager)\b/i));
  const isExplicitFileSearch = targetKind === 'file_or_folder' || (!isExplorerApp && (Boolean(pathChoice) || Boolean(targetQuery.match(/\b(folder|file|document|dir)\b/i))));
  const isAppTarget = isExplorerApp || targetKind === 'application' || (!isExplicitFileSearch && (
    appId || (APP_REGISTRY && APP_REGISTRY.some(a => a.id === targetQuery.toLowerCase() || (a.aliases && a.aliases.includes(targetQuery.toLowerCase()))))
  ));
  const targetLabel = displayName || appId || targetQuery;
  const normalizedCandidate = (appId || displayName || targetQuery || '').trim().toLowerCase();

  // ── Web Application Direct Routing (e.g. YouTube, Netflix, ChatGPT) ───────────
  const webAppEntry = !isExplicitFileSearch && APP_REGISTRY && APP_REGISTRY.find(
    (a) => a.type === 'web' && (
      (appId && a.id === appId.toLowerCase()) ||
      a.id === normalizedCandidate ||
      (a.aliases && a.aliases.includes(normalizedCandidate)) ||
      (new RegExp('\\b' + a.id + '\\b', 'i')).test(normalizedCandidate) ||
      (a.aliases && a.aliases.some(alias => (new RegExp('\\b' + alias + '\\b', 'i')).test(normalizedCandidate)))
    )
  );

  if (webAppEntry) {
    console.log(`[Electron] Direct routing for web application "${webAppEntry.displayName}" query="${effectiveQuery}" actionType="${effectiveActionType}"`);
    broadcastProgress({
      step: 1,
      phase: 'finding',
      targetName: webAppEntry.displayName,
      message: `Connecting to ${webAppEntry.displayName}...`,
    });
    broadcastProgress({
      step: 2,
      phase: 'destination_found',
      targetName: webAppEntry.displayName,
      message: `${webAppEntry.displayName} web service ready.`,
    });
    broadcastProgress({
      step: 4,
      phase: 'opening',
      targetName: webAppEntry.displayName,
      message: effectiveQuery
        ? (effectiveActionType === 'play'
            ? `Playing "${effectiveQuery}" on ${webAppEntry.displayName}...`
            : (effectiveActionType === 'search'
                ? `Searching "${effectiveQuery}" on ${webAppEntry.displayName}...`
                : `Opening ${webAppEntry.displayName} for "${effectiveQuery}" in browser...`))
        : `Opening ${webAppEntry.displayName} in browser...`,
    });

    const launchResult = await launchApp(webAppEntry.id, { query: effectiveQuery, actionType: effectiveActionType });
    const finalPhase = launchResult.success ? 'success' : 'failed';
    const finalMessage = launchResult.message || (launchResult.success ? `Opened ${launchResult.displayName}` : (launchResult.error || 'Failed to open web application'));

    broadcastProgress({
      step: 5,
      phase: finalPhase,
      targetName: webAppEntry.displayName,
      message: finalMessage,
    });

    if (avatarWindow && !avatarWindow.isDestroyed()) {
      avatarWindow.webContents.send('companion:sync-state', {
        avatarState: launchResult.success ? 'Success' : 'Error',
        taskState: finalPhase,
        isMoving: false,
      });
    }

    return {
      success: launchResult.success,
      verified: launchResult.verified,
      displayName: launchResult.displayName,
      message: finalMessage,
      executionMode,
      targetInfo: {
        status: 'found',
        destinationType: 'web-service',
        explanation: `Opened ${webAppEntry.displayName} web service in browser`,
      },
    };
  }

  // ── Stage 1: Searching for the requested target ────────────────────────────
  const stage1Msg = isAppTarget
    ? `Searching for ${targetLabel}...`
    : `Searching for "${targetLabel}"...`;

  broadcastProgress({
    step: 1,
    phase: 'finding',
    targetName: targetLabel,
    message: stage1Msg,
  });

  // ── Stage 2: Destination Resolution (App Discovery vs File Discovery) ──────
  let targetInfo;
  try {
    targetInfo = await resolveDestination(targetQuery, { workArea, scaleFactor }, pathChoice, targetKind || 'auto');
  } catch (err) {
    console.error('[Electron] resolveDestination error:', err);
    targetInfo = { status: 'not_found', explanation: err.message };
  }

  console.log('[Electron] Resolved targetInfo:', targetInfo);

  // If multiple matching results exist in system search -> ask user to clarify
  if (targetInfo.status === 'clarification_required') {
    const clarMsg = `Found ${targetInfo.matches.length} matching locations for "${targetInfo.targetName}". Please clarify which location you would like to open.`;
    broadcastProgress({
      step: 2,
      phase: 'clarification_required',
      targetName: targetInfo.targetName,
      matches: targetInfo.matches,
      message: clarMsg,
    });
    return {
      success: false,
      clarificationRequired: true,
      matches: targetInfo.matches,
      displayName: targetInfo.targetName,
      targetInfo,
      message: clarMsg,
    };
  }

  // If item was not found anywhere
  if (targetInfo.status === 'not_found' || !targetInfo.found) {
    // Check if it is a hybrid app in APP_REGISTRY with webUrl, searchUrl, or fallbackUrl (e.g. Spotify, WhatsApp)
    const hybridEntry = !isExplicitFileSearch && APP_REGISTRY && APP_REGISTRY.find(
      (a) => (appId && a.id === appId.toLowerCase()) ||
             a.id === normalizedCandidate ||
             (a.aliases && a.aliases.includes(normalizedCandidate)) ||
             (new RegExp('\\b' + a.id + '\\b', 'i')).test(normalizedCandidate) ||
             (a.aliases && a.aliases.some(alias => (new RegExp('\\b' + alias + '\\b', 'i')).test(normalizedCandidate)))
    );

    if (hybridEntry && (hybridEntry.searchUrl || hybridEntry.webUrl || hybridEntry.fallbackUrl)) {
      console.log(`[Electron] Native target for "${hybridEntry.displayName}" not found, falling back to web player`);
      broadcastProgress({
        step: 4,
        phase: 'opening',
        targetName: hybridEntry.displayName,
        message: effectiveQuery
          ? (effectiveActionType === 'play'
              ? `Playing "${effectiveQuery}" on ${hybridEntry.displayName} Web Player...`
              : `Opening ${hybridEntry.displayName} for "${effectiveQuery}" in browser...`)
          : `Opening ${hybridEntry.displayName} in browser...`,
      });

      const launchResult = await launchApp(hybridEntry.id, { query: effectiveQuery, actionType: effectiveActionType });
      const finalPhase = launchResult.success ? 'success' : 'failed';
      const finalMessage = launchResult.message || (launchResult.success ? `Opened ${launchResult.displayName}` : (launchResult.error || 'Failed to launch web fallback'));

      broadcastProgress({
        step: 5,
        phase: finalPhase,
        targetName: hybridEntry.displayName,
        message: finalMessage,
      });

      if (avatarWindow && !avatarWindow.isDestroyed()) {
        avatarWindow.webContents.send('companion:sync-state', {
          avatarState: launchResult.success ? 'Success' : 'Error',
          taskState: finalPhase,
          isMoving: false,
        });
      }

      return {
        success: launchResult.success,
        verified: launchResult.verified,
        displayName: launchResult.displayName,
        message: finalMessage,
        executionMode,
        targetInfo: {
          status: 'found',
          destinationType: 'web-fallback',
          explanation: `Opened ${hybridEntry.displayName} via web player`,
        },
      };
    }

    const errorMsg = targetInfo.explanation || `Could not find "${targetQuery}" in installed applications or desktop shortcuts.`;
    broadcastProgress({
      step: 5,
      phase: 'failed',
      targetName: targetLabel,
      error: errorMsg,
      message: errorMsg,
    });
    if (avatarWindow && !avatarWindow.isDestroyed()) {
      avatarWindow.webContents.send('companion:sync-state', {
        avatarState: 'Error',
        taskState: 'failed',
        isMoving: false,
      });
    }
    return {
      success: false,
      verified: false,
      displayName: targetLabel,
      error: errorMsg,
      targetInfo,
    };
  }

  let moveResult = { completed: true, cancelled: false };
  let openSuccess = false;
  let verified = false;
  let openError = null;

  const ensureStandaloneAvatar = () => {
    if (avatarWindow && !avatarWindow.isDestroyed()) {
      const [currW, currH] = avatarWindow.getSize();
      if (currW > AVATAR_CONFIG.windowWidth || currH > AVATAR_CONFIG.windowHeight) {
        const [currX, currY] = avatarWindow.getPosition();
        avatarWindow.setBounds({
          x: currX,
          y: Math.round(currY + (currH - AVATAR_CONFIG.windowHeight)),
          width: AVATAR_CONFIG.windowWidth,
          height: AVATAR_CONFIG.windowHeight,
        });
        avatarWindow.webContents.send('companion:sync-state', {
          chatboxOpen: false,
        });
      }
    }
  };

  try {
    if (targetInfo.discoveryType === 'application') {
      if (targetInfo.foundOnDesktop) {
        // ── APPLICATION SCENARIO A: Target shortcut exists on Desktop ────────────────
        broadcastProgress({
          step: 2,
          phase: 'destination_found',
          targetName: targetInfo.targetName,
          destination: targetInfo.destination,
          message: `${targetInfo.targetName} found.`,
        });

        broadcastProgress({
          step: 3,
          phase: 'walking',
          targetName: targetInfo.targetName,
          destination: targetInfo.destination,
          message: `Doraemon is moving towards ${targetInfo.targetName}...`,
        });

        if (avatarWindow && !avatarWindow.isDestroyed()) {
          ensureStandaloneAvatar();
          avatarWindow.show();
          avatarWindow.setAlwaysOnTop(true, 'screen-saver');
          avatarWindow.webContents.send('companion:sync-state', {
            avatarState: 'Working',
            taskState: 'launching',
            isMoving: true,
            chatboxOpen: false,
          });

          moveResult = await moveAvatarTo(avatarWindow, targetInfo.destination.x, targetInfo.destination.y, { durationMs: 1400 });
        }

        if (moveResult.cancelled) {
          broadcastProgress({ step: 5, phase: 'cancelled', message: 'Movement cancelled by user.' });
          return { success: false, cancelled: true, displayName: targetInfo.targetName, error: 'Movement cancelled by user' };
        }

        broadcastProgress({
          step: 4,
          phase: 'opening',
          targetName: targetInfo.targetName,
          message: `Opening ${targetInfo.targetName}...`,
        });

        if (executionMode === 'mock') {
          openSuccess = true;
          verified = true;
        } else {
          const { exec } = require('child_process');
          if (targetInfo.launchTarget) {
            exec(`cmd.exe /c start "" "${targetInfo.launchTarget}"`);
          } else {
            await launchApp(appId || targetInfo.targetName, { query });
          }
          const processCandidates = getCanonicalProcessNames(targetInfo.targetName, targetInfo.processNames || []);
          verified = await waitForProcess(processCandidates, 4000);
          openSuccess = verified;
          if (!openSuccess) {
            const fallbackLaunch = await launchApp(appId || targetInfo.targetName, { query });
            openSuccess = fallbackLaunch.success;
            verified = fallbackLaunch.verified;
            if (!openSuccess) openError = fallbackLaunch.error || `Process verification timed out for ${targetInfo.targetName} in Windows tasklist.`;
          }
        }
      } else {
        // ── APPLICATION SCENARIO B: No Desktop shortcut -> Start / Search Navigation ──
        broadcastProgress({
          step: 2,
          phase: 'destination_found',
          targetName: targetInfo.targetName,
          message: `${targetInfo.targetName} found.`,
        });

        const startBtn = await getStartButtonCoordinates({ workArea, scaleFactor });
        const startDestX = Math.max(workArea.x + 8, Math.min(startBtn.X - Math.round(AVATAR_CONFIG.windowWidth / 2), workArea.x + workArea.width - AVATAR_CONFIG.windowWidth - 8));
        const startDestY = Math.max(workArea.y + 8, workArea.y + workArea.height - AVATAR_CONFIG.windowHeight);

        // Step 1: Doraemon moves directly towards the Windows Start button
        broadcastProgress({
          step: 3,
          phase: 'walking',
          targetName: targetInfo.targetName,
          message: `Doraemon is moving towards the Start button...`,
        });

        if (avatarWindow && !avatarWindow.isDestroyed()) {
          ensureStandaloneAvatar();
          avatarWindow.show();
          avatarWindow.setAlwaysOnTop(true, 'screen-saver');
          avatarWindow.webContents.send('companion:sync-state', {
            avatarState: 'Working',
            taskState: 'launching',
            isMoving: true,
            chatboxOpen: false,
          });

          moveResult = await moveAvatarTo(avatarWindow, startDestX, startDestY, { durationMs: 1200 });
          if (moveResult.cancelled) {
            broadcastProgress({ step: 5, phase: 'cancelled', message: 'Movement cancelled by user.' });
            return { success: false, cancelled: true, displayName: targetInfo.targetName, error: 'Movement cancelled by user' };
          }
        }

        // Step 2: Open Windows Search interface
        broadcastProgress({
          step: 2,
          phase: 'opening_search',
          targetName: targetInfo.targetName,
          message: 'Opening Windows Search...',
        });

        const searchBox = await openStartAndGetSearchBox({ workArea, scaleFactor });

        // Calculate Search panel bounds and Doraemon position BESIDE the Search field
        const panelWidth = searchBox.Panel?.Width || 720;
        const panelLeft = searchBox.Panel?.X || Math.round(workArea.x + (workArea.width - panelWidth) / 2);
        const panelRight = panelLeft + panelWidth;
        const searchBoxY = searchBox.Y || (workArea.y + workArea.height - 650);

        // Position Doraemon BESIDE the search panel near the search input field without overlapping
        const hasLeftClearance = (panelLeft - workArea.x) >= (AVATAR_CONFIG.windowWidth + 14);
        let searchDestX;
        let facingBeside;
        if (hasLeftClearance) {
          searchDestX = Math.max(workArea.x + 8, panelLeft - AVATAR_CONFIG.windowWidth - 14);
          facingBeside = 'right'; // Facing right towards the Search panel
        } else {
          searchDestX = Math.min(panelRight + 14, workArea.x + workArea.width - AVATAR_CONFIG.windowWidth - 8);
          facingBeside = 'left'; // Facing left towards the Search panel
        }
        const searchDestY = Math.max(workArea.y + 12, Math.min(searchBoxY - 30, workArea.y + workArea.height - AVATAR_CONFIG.windowHeight - 12));

        // Step 3: Move Doraemon beside the Search field
        broadcastProgress({
          step: 3,
          phase: 'moving_to_search_field',
          targetName: targetInfo.targetName,
          message: 'Doraemon is moving towards the Search field...',
        });

        if (avatarWindow && !avatarWindow.isDestroyed()) {
          avatarWindow.setAlwaysOnTop(true, 'screen-saver');
          moveResult = await moveAvatarTo(avatarWindow, searchDestX, searchDestY, { durationMs: 900, facing: facingBeside });
          if (moveResult.cancelled) {
            await closeStartMenu();
            broadcastProgress({ step: 5, phase: 'cancelled', message: 'Movement cancelled by user.' });
            return { success: false, cancelled: true, displayName: targetInfo.targetName, error: 'Movement cancelled by user' };
          }
          avatarWindow.webContents.send('companion:sync-state', {
            avatarState: 'Working',
            facing: facingBeside,
            isMoving: false,
          });
        }

        // Step 4: Enter search query and wait for real results
        broadcastProgress({
          step: 4,
          phase: 'searching',
          targetName: targetInfo.targetName,
          message: `Searching for ${targetInfo.targetName}...`,
        });

        if (avatarWindow && !avatarWindow.isDestroyed()) {
          avatarWindow.setAlwaysOnTop(true, 'screen-saver');
        }

        const searchResult = await searchAndGetResultCoordinates(targetInfo.targetName, { workArea, scaleFactor });

        if (!searchResult || !searchResult.Found) {
          await closeStartMenu();
          const failReason = searchResult?.Reason || `Could not find ${targetInfo.targetName} in Windows Search results or installed applications.`;
          broadcastProgress({
            step: 5,
            phase: 'failed',
            targetName: targetInfo.targetName,
            error: failReason,
            message: failReason,
          });
          if (avatarWindow && !avatarWindow.isDestroyed()) {
            avatarWindow.webContents.send('companion:sync-state', { avatarState: 'Error', taskState: 'failed', isMoving: false });
          }
          return { success: false, verified: false, displayName: targetInfo.targetName, error: failReason };
        }

        // Step 5: Search results found
        broadcastProgress({
          step: 5,
          phase: 'results_found',
          targetName: targetInfo.targetName,
          message: 'Search results found.',
        });

        const selectedResultName = searchResult.Name || targetInfo.targetName;

        // Step 6: Move Doraemon towards the selected result while staying beside the panel
        broadcastProgress({
          step: 6,
          phase: 'moving_to_result',
          targetName: targetInfo.targetName,
          message: `Doraemon is moving towards ${selectedResultName}...`,
        });

        if (avatarWindow && !avatarWindow.isDestroyed()) {
          avatarWindow.setAlwaysOnTop(true, 'screen-saver');
          const resY = searchResult.Y || (searchBoxY + 84);
          const resDestY = Math.max(workArea.y + 12, Math.min(resY - 40, workArea.y + workArea.height - AVATAR_CONFIG.windowHeight - 12));
          moveResult = await moveAvatarTo(avatarWindow, searchDestX, resDestY, { durationMs: 800, facing: facingBeside });
          if (moveResult.cancelled) {
            await closeStartMenu();
            broadcastProgress({ step: 5, phase: 'cancelled', message: 'Movement cancelled by user.' });
            return { success: false, cancelled: true, displayName: targetInfo.targetName, error: 'Movement cancelled by user' };
          }
        }

        // Step 7: Open the application
        broadcastProgress({
          step: 7,
          phase: 'opening',
          targetName: targetInfo.targetName,
          message: `Opening ${targetInfo.targetName}...`,
        });

        if (executionMode === 'mock') {
          openSuccess = true;
          verified = true;
        } else {
          const { exec } = require('child_process');
          const isExplorerApp = (targetInfo.targetName && targetInfo.targetName.toLowerCase().includes('explorer')) ||
            (targetInfo.launchTarget && targetInfo.launchTarget.toLowerCase().includes('explorer')) ||
            (targetInfo.processNames && targetInfo.processNames.includes('explorer.exe'));

          if (isExplorerApp) {
            exec('cmd.exe /c start "" explorer.exe');
            verified = true;
            openSuccess = true;
          } else if (targetInfo.launchType === 'packaged' && targetInfo.appUserModelId) {
            exec(`cmd.exe /c start shell:AppsFolder\\${targetInfo.appUserModelId}`);
            const processCandidates = getCanonicalProcessNames(targetInfo.targetName, targetInfo.processNames || []);
            verified = await waitForProcess(processCandidates, 4000);
            openSuccess = verified;
          } else if (targetInfo.launchTarget) {
            exec(`cmd.exe /c start "" "${targetInfo.launchTarget}"`);
            const processCandidates = getCanonicalProcessNames(targetInfo.targetName, targetInfo.processNames || []);
            verified = await waitForProcess(processCandidates, 4000);
            openSuccess = verified;
          } else {
            const launchRes = await launchApp(appId || targetInfo.targetName, { query });
            openSuccess = launchRes.success;
            verified = launchRes.verified;
            openError = launchRes.error;
          }

          if (!openSuccess && !openError) {
            openError = `Process verification timed out for ${targetInfo.targetName} in Windows tasklist.`;
          }
        }
        await closeStartMenu();
      }
    } else {
      // ── FILE OR FOLDER DISCOVERY ROUTE ─────────────────────────────────────
      broadcastProgress({
        step: 1,
        phase: 'finding',
        targetName: targetInfo.targetName,
        message: targetInfo.foundOnDesktop
          ? `Found "${targetInfo.targetName}" directly on Windows Desktop.`
          : `Searching system folders for "${targetInfo.targetName}"...`,
      });

      broadcastProgress({
        step: 3,
        phase: 'walking',
        targetName: targetInfo.targetName,
        destination: targetInfo.destination,
        message: `Doraemon is moving towards ${targetInfo.targetName}...`,
      });

      if (avatarWindow && !avatarWindow.isDestroyed()) {
        ensureStandaloneAvatar();
        avatarWindow.show();
        avatarWindow.webContents.send('companion:sync-state', {
          avatarState: 'Working',
          taskState: 'launching',
          isMoving: true,
          chatboxOpen: false,
        });

        moveResult = await moveAvatarTo(avatarWindow, targetInfo.destination.x, targetInfo.destination.y, { durationMs: 1400 });
      }

      if (moveResult.cancelled) {
        broadcastProgress({ step: 5, phase: 'cancelled', message: 'Movement cancelled by user.' });
        return { success: false, cancelled: true, displayName: targetInfo.targetName, error: 'Movement cancelled by user' };
      }

      broadcastProgress({
        step: 4,
        phase: 'opening',
        targetName: targetInfo.targetName,
        message: `Opening ${targetInfo.targetName}...`,
      });

      if (executionMode === 'mock') {
        openSuccess = true;
        verified = true;
      } else {
        const { exec } = require('child_process');
        if (targetInfo.isFolder) {
          exec(`cmd.exe /c start "" explorer.exe "${targetInfo.targetPath}"`);
        } else {
          exec(`cmd.exe /c start "" "${targetInfo.targetPath}"`);
        }
        openSuccess = true;
        verified = true;
      }
    }
  } catch (err) {
    openSuccess = false;
    openError = err.message;
  }

  // ── Stage 6: Success or actual failure ──────────────────────────────────────
  const finalState = openSuccess ? 'success' : 'failed';
  const finalMsg = openSuccess
    ? `${targetInfo.targetName} successfully opened!`
    : `Failed to open ${targetInfo.targetName}: ${openError || 'Process launch could not be verified'}`;

  broadcastProgress({
    step: 6,
    phase: finalState,
    success: openSuccess,
    verified,
    targetName: targetInfo.targetName,
    error: openError,
    message: finalMsg,
  });

  if (avatarWindow && !avatarWindow.isDestroyed()) {
    avatarWindow.webContents.send('companion:sync-state', {
      avatarState: openSuccess ? 'Success' : 'Error',
      taskState: finalState,
      isMoving: false,
    });
  }

  return {
    success: openSuccess,
    verified,
    taskState: finalState,
    displayName: targetInfo.targetName,
    targetInfo,
    executionMode,
    message: finalMsg,
    error: openError,
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
    const targetW = AVATAR_CONFIG.chatboxWidth;
    const targetH = AVATAR_CONFIG.chatboxHeight;
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
    const targetW = AVATAR_CONFIG.windowWidth;
    const targetH = AVATAR_CONFIG.windowHeight;
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
