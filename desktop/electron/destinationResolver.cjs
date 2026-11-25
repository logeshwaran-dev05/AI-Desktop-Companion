/**
 * DESTINATION-BASED DESKTOP RESOLVER
 * ===================================
 * Implements two independent, robust discovery systems for Windows:
 *
 * A. Application Discovery & Launching:
 *    Searches in exact priority order:
 *    1. Desktop shortcuts (.lnk on Desktop with physical COM IFolderView screen coordinates).
 *    2. Start Menu shortcuts (Current user and All users).
 *    3. Windows registered application entries (Uninstall keys).
 *    4. App Paths registry entries.
 *    5. Executables available through PATH.
 *    6. Windows packaged applications (AppUserModelIDs via Get-StartApps, e.g. Calculator, Notepad).
 *
 *    Navigation:
 *    - If shortcut exists on Desktop: Doraemon walks directly to the desktop icon coordinates.
 *    - If no Desktop shortcut exists: Doraemon uses the visible Windows Start / App launcher route.
 *
 * B. File & Folder Discovery:
 *    1. Check Windows Desktop.
 *    2. Fallback to user libraries and indexed folders (Downloads, Documents, Pictures, etc.).
 *    3. Multi-match clarification with user choice.
 *    4. Highlights target in File Explorer and moves Doraemon directly to the Explorer window.
 */

const { execFile, exec } = require('child_process');
const path = require('path');

const ICON_FINDER_PS1 = path.join(__dirname, 'desktopIconFinder.ps1');
const FILE_SEARCH_PS1 = path.join(__dirname, 'systemFileSearch.ps1');
const APP_FINDER_PS1 = path.join(__dirname, 'appFinder.ps1');
const WINDOWS_SEARCH_PS1 = path.join(__dirname, 'windowsSearchAutomation.ps1');

let cachedDesktopIcons = null;
let lastCacheTime = 0;
const CACHE_TTL_MS = 2500;

/**
 * Common app aliases mapped to canonical names or desktop search terms
 */
const COMMON_APP_ALIASES = {
  notepad: ['notepad', 'notes', 'text editor', 'textpad'],
  calculator: ['calculator', 'calc', 'math'],
  explorer: ['file explorer', 'explorer', 'my computer', 'folders'],
  chrome: ['google chrome', 'chrome', 'browser', 'google-chrome'],
  firefox: ['firefox', 'mozilla firefox'],
  vscode: ['visual studio code', 'vscode', 'code'],
  whatsapp: ['whatsapp'],
  spotify: ['spotify', 'music'],
  youtube: ['youtube'],
  github: ['github desktop', 'github'],
  postman: ['postman'],
  vlc: ['vlc media player', 'vlc'],
  terminal: ['command prompt', 'cmd', 'powershell', 'windows powershell'],
  paint: ['paint', 'mspaint', 'draw'],
};

/**
 * Canonical Windows Process Name Mapping.
 * Crucial for reliable process detection in Windows tasklist.
 */
const CANONICAL_APP_PROCESSES = {
  chrome: ['chrome.exe'],
  'google chrome': ['chrome.exe'],
  googlechrome: ['chrome.exe'],
  edge: ['msedge.exe'],
  'microsoft edge': ['msedge.exe'],
  msedge: ['msedge.exe'],
  notepad: ['notepad.exe'],
  calculator: ['CalculatorApp.exe', 'Calculator.exe', 'calc.exe'],
  calc: ['CalculatorApp.exe', 'Calculator.exe', 'calc.exe'],
  explorer: ['explorer.exe'],
  'file explorer': ['explorer.exe'],
  vscode: ['Code.exe', 'code.exe'],
  'visual studio code': ['Code.exe', 'code.exe'],
  code: ['Code.exe', 'code.exe'],
  paint: ['mspaint.exe', 'PaintStudio.View.exe'],
  mspaint: ['mspaint.exe'],
  taskmgr: ['Taskmgr.exe', 'taskmgr.exe'],
  'task manager': ['Taskmgr.exe', 'taskmgr.exe'],
  cmd: ['cmd.exe', 'conhost.exe'],
  'command prompt': ['cmd.exe', 'conhost.exe'],
  terminal: ['WindowsTerminal.exe', 'cmd.exe', 'powershell.exe'],
  powershell: ['powershell.exe', 'pwsh.exe'],
  'windows powershell': ['powershell.exe'],
  spotify: ['Spotify.exe', 'spotify.exe'],
  whatsapp: ['WhatsApp.exe', 'WhatsAppNative.exe'],
  slack: ['slack.exe'],
  discord: ['Discord.exe'],
  zoom: ['Zoom.exe'],
  word: ['WINWORD.EXE', 'winword.exe'],
  excel: ['EXCEL.EXE', 'excel.exe'],
  powerpoint: ['POWERPNT.EXE', 'powerpnt.exe'],
};

/**
 * Resolves all possible executable process image names for a given application target
 * @param {string} appNameOrTarget
 * @param {string[]} existingProcesses
 * @returns {string[]} Deduplicated list of process names (e.g. ['chrome.exe', 'Google Chrome.exe'])
 */
function getCanonicalProcessNames(appNameOrTarget, existingProcesses = []) {
  const result = new Set();

  if (Array.isArray(existingProcesses)) {
    existingProcesses.forEach((p) => {
      if (typeof p === 'string' && p.trim()) result.add(p.trim());
    });
  }

  if (typeof appNameOrTarget === 'string' && appNameOrTarget.trim()) {
    const raw = appNameOrTarget.trim();
    const lower = raw.toLowerCase();

    // Check exact canonical map match
    if (CANONICAL_APP_PROCESSES[lower]) {
      CANONICAL_APP_PROCESSES[lower].forEach((p) => result.add(p));
    }

    // Check substring or keyword match in canonical map
    for (const [key, procs] of Object.entries(CANONICAL_APP_PROCESSES)) {
      if (lower === key || lower.includes(key) || key.includes(lower)) {
        procs.forEach((p) => result.add(p));
      }
    }

    // Stripped alphanumeric + .exe (e.g. "googlechrome.exe")
    const noSpaces = lower.replace(/[^a-z0-9]/g, '');
    if (noSpaces) {
      result.add(`${noSpaces}.exe`);
    }

    if (lower.endsWith('.exe')) {
      result.add(path.basename(raw));
    } else {
      result.add(`${raw}.exe`);
    }
  }

  return Array.from(result);
}

/**
 * Executes a PowerShell script safely and returns stdout
 * @param {string} scriptPath
 * @param {string[]} args
 * @returns {Promise<string>}
 */
function runPowerShellScript(scriptPath, args = []) {
  return new Promise((resolve) => {
    const psArgs = [
      '-NoProfile',
      '-NonInteractive',
      '-ExecutionPolicy',
      'Bypass',
      '-File',
      scriptPath,
      ...args,
    ];

    execFile('powershell.exe', psArgs, { timeout: 15000, maxBuffer: 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) {
        console.warn(`[DestinationResolver] PowerShell error on ${scriptPath}:`, stderr || err.message);
        resolve('[]');
      } else {
        resolve(stdout.trim());
      }
    });
  });
}

/**
 * Queries real-time Windows Desktop icons and their exact screen coordinates
 * @param {boolean} forceRefresh
 * @returns {Promise<Array<{ Name: string, CleanName: string, Path: string, X: number, Y: number, IsFolder: boolean, IsLnk: boolean }>>}
 */
async function getDesktopIcons(forceRefresh = false) {
  const now = Date.now();
  if (!forceRefresh && cachedDesktopIcons && now - lastCacheTime < CACHE_TTL_MS) {
    return cachedDesktopIcons;
  }

  try {
    const rawJson = await runPowerShellScript(ICON_FINDER_PS1);
    const parsed = JSON.parse(rawJson || '[]');
    cachedDesktopIcons = Array.isArray(parsed) ? parsed : [];
    lastCacheTime = now;
    return cachedDesktopIcons;
  } catch (err) {
    console.error('[DestinationResolver] Failed to parse desktop icons:', err.message);
    return [];
  }
}

/**
 * Queries Windows for installed applications matching query across:
 * 1. Start Menu shortcuts (User & System)
 * 2. Windows App Paths registry entries
 * 3. Executables available through PATH
 * 4. Windows Packaged Applications (AppUserModelIDs via Get-StartApps)
 * 5. Windows Registered Application entries
 * @param {string} query
 * @returns {Promise<{ Found: boolean, Source?: string, DisplayName?: string, Path?: string, LaunchTarget?: string, LaunchType?: string, AppUserModelId?: string, ProcessNames?: string[], SourceDescription?: string }>}
 */
async function searchInstalledApplication(query) {
  try {
    const rawJson = await runPowerShellScript(APP_FINDER_PS1, ['-query', query]);
    const parsed = JSON.parse(rawJson || '{}');
    return parsed;
  } catch (err) {
    console.error('[DestinationResolver] Failed to search installed application:', err.message);
    return { Found: false };
  }
}

/**
 * Obtains actual screen coordinates of the Windows Start button
 * @param {object} displayInfo
 * @returns {Promise<{ Found: boolean, X: number, Y: number, BoundingBox: object }>}
 */
async function getStartButtonCoordinates(displayInfo = {}) {
  const workArea = displayInfo.workArea || { x: 0, y: 0, width: 1536, height: 816 };
  const isCentered = true;
  const btnX = isCentered
    ? Math.round(workArea.x + (workArea.width / 2) - 180)
    : Math.round(workArea.x + 32);
  const btnY = Math.round(workArea.y + workArea.height + 24);

  return {
    Found: true,
    X: btnX,
    Y: btnY,
    BoundingBox: { X: btnX - 20, Y: btnY - 20, Width: 40, Height: 40 },
    Method: 'TaskbarGeometry',
    IsCentered: isCentered,
  };
}

/**
 * Opens Start Menu and returns coordinates of the actual Windows Search box
 * @param {object} displayInfo
 * @returns {Promise<{ Found: boolean, X: number, Y: number, BoundingBox: object }>}
 */
async function openStartAndGetSearchBox(displayInfo = {}) {
  const workArea = displayInfo.workArea || { x: 0, y: 0, width: 1536, height: 816 };
  const raw = await runPowerShellScript(WINDOWS_SEARCH_PS1, [
    '-Action', 'OpenStartAndGetSearchBox',
    '-WorkAreaX', String(workArea.x),
    '-WorkAreaY', String(workArea.y),
    '-WorkAreaWidth', String(workArea.width),
    '-WorkAreaHeight', String(workArea.height),
    '-ScaleFactor', String(displayInfo.scaleFactor || 1.0),
  ]);
  try {
    return JSON.parse(raw || '{}');
  } catch {
    return { Found: false };
  }
}

/**
 * Types search query into Windows Search and retrieves screen coordinates of matching result
 * @param {string} query
 * @param {object} displayInfo
 * @returns {Promise<{ Found: boolean, X: number, Y: number, Name: string, BoundingBox: object, Reason?: string }>}
 */
async function searchAndGetResultCoordinates(query, displayInfo = {}) {
  const workArea = displayInfo.workArea || { x: 0, y: 0, width: 1536, height: 816 };
  const raw = await runPowerShellScript(WINDOWS_SEARCH_PS1, [
    '-Action', 'SearchAndGetResult',
    '-Query', query,
    '-WorkAreaX', String(workArea.x),
    '-WorkAreaY', String(workArea.y),
    '-WorkAreaWidth', String(workArea.width),
    '-WorkAreaHeight', String(workArea.height),
    '-ScaleFactor', String(displayInfo.scaleFactor || 1.0),
  ]);
  try {
    return JSON.parse(raw || '{}');
  } catch {
    return { Found: false, Reason: 'PowerShell search execution failed' };
  }
}

/**
 * Closes the Start Menu if still open
 */
async function closeStartMenu() {
  await runPowerShellScript(WINDOWS_SEARCH_PS1, ['-Action', 'CloseStart']);
}

/**
 * Searches the computer for files or folders matching query
 * @param {string} query
 * @returns {Promise<Array<{ name: string, baseName: string, path: string, isFolder: boolean, extension: string }>>}
 */
async function searchSystemFiles(query) {
  try {
    const rawJson = await runPowerShellScript(FILE_SEARCH_PS1, ['-query', query]);
    const parsed = JSON.parse(rawJson || '[]');
    if (Array.isArray(parsed)) return parsed;
    if (parsed && typeof parsed === 'object') return [parsed];
    return [];
  } catch (err) {
    console.error('[DestinationResolver] Failed to search system files:', err.message);
    return [];
  }
}

/**
 * Locates an open File Explorer window via COM and gets its bounds
 * @param {string} targetPath
 * @returns {Promise<{ left: number, top: number, width: number, height: number }>}
 */
function getExplorerWindowBounds(targetPath) {
  return new Promise((resolve) => {
    const psCmd = `
$shell = New-Object -ComObject Shell.Application
$targetParent = [System.IO.Path]::GetDirectoryName("${targetPath.replace(/\\/g, '\\\\')}")
$found = $null
foreach ($w in $shell.Windows()) {
  try {
    $p = $w.Document.Folder.Self.Path
    if ($p -and ($targetParent.StartsWith($p) -or $p.StartsWith($targetParent))) {
      $found = $w
      break
    }
  } catch {}
}
if (-not $found -and $shell.Windows().Count -gt 0) {
  $found = $shell.Windows().Item(0)
}
if ($found) {
  Write-Output "$($found.Left)|$($found.Top)|$($found.Width)|$($found.Height)"
} else {
  Write-Output "100|100|800|600"
}
`;
    exec(`powershell -NoProfile -NonInteractive -Command "${psCmd.replace(/\n/g, ' ')}"`, (err, stdout) => {
      const parts = (stdout || '').trim().split('|').map((n) => parseInt(n, 10));
      if (parts.length === 4 && !parts.some(isNaN)) {
        resolve({ left: parts[0], top: parts[1], width: parts[2], height: parts[3] });
      } else {
        resolve({ left: 100, top: 100, width: 800, height: 600 });
      }
    });
  });
}

/**
 * Extracts candidate target names from natural language commands
 * @param {string} rawCommand
 * @returns {string[]} Ordered list of search candidate strings
 */
function extractTargetCandidates(rawCommand) {
  const clean = (rawCommand || '')
    .trim()
    .replace(/^please\s+/i, '')
    .replace(/^can\s+you\s+/i, '')
    .replace(/^could\s+you\s+/i, '')
    .replace(/^i\s+want\s+to\s+/i, '');

  const candidates = [];

  // Match "open/launch/start/show folder X" or "open/launch/start/show file X" or "open X"
  const actionMatch = clean.match(/^(?:open|launch|start|run|show|access|find|goto)\s+(?:the\s+)?(?:folder\s+|file\s+|app\s+|application\s+)?(.+)$/i);
  if (actionMatch && actionMatch[1]) {
    const target = actionMatch[1].trim().replace(/[?.!]+$/, '');
    candidates.push(target);
  }

  // Also add original cleaned text
  if (!candidates.includes(clean)) {
    candidates.push(clean);
  }

  return candidates;
}

/**
 * Searches Desktop icons for candidate matches
 * @param {string[]} candidates
 * @param {Array} desktopIcons
 * @returns {object|null} Matched Desktop icon
 */
function findDesktopIconMatch(candidates, desktopIcons) {
  for (const candidate of candidates) {
    const candLower = candidate.toLowerCase();

    // 1. Exact match on clean name
    let matched = desktopIcons.find(
      (icon) => icon.CleanName && icon.CleanName.toLowerCase() === candLower
    );
    if (matched) return matched;

    // 2. Exact match on full name
    matched = desktopIcons.find(
      (icon) => icon.Name && icon.Name.toLowerCase() === candLower
    );
    if (matched) return matched;

    // 3. Substring match
    matched = desktopIcons.find(
      (icon) => icon.CleanName && icon.CleanName.toLowerCase().includes(candLower)
    );
    if (matched) return matched;

    // 4. Common app alias match
    for (const [appKey, aliases] of Object.entries(COMMON_APP_ALIASES)) {
      if (aliases.some((a) => a === candLower || candLower.includes(a)) || appKey === candLower) {
        matched = desktopIcons.find((icon) => {
          const iconClean = (icon.CleanName || '').toLowerCase();
          return aliases.some((a) => iconClean.includes(a)) || iconClean.includes(appKey);
        });
        if (matched) return matched;
      }
    }
  }
  return null;
}

/**
 * ─────────────────────────────────────────────────────────────────────────────
 * DISCOVERY SYSTEM A: Application Discovery and Launching
 * ─────────────────────────────────────────────────────────────────────────────
 * Priority search order:
 * 1. Desktop shortcuts.
 * 2. Start Menu shortcuts (User & System).
 * 3. Windows registered application entries.
 * 4. App Paths registry entries.
 * 5. Executables available through PATH.
 * 6. Windows packaged applications (AppUserModelIDs).
 *
 * @param {string} rawCommand
 * @param {object} displayInfo
 * @returns {Promise<object>}
 */
async function discoverApplication(rawCommand, displayInfo = {}) {
  const workArea = displayInfo.workArea || { x: 0, y: 0, width: 1536, height: 816 };
  const scaleFactor = displayInfo.scaleFactor || 1.0;

  const candidates = extractTargetCandidates(rawCommand);
  const primaryCandidate = candidates[0] || rawCommand.trim();

  console.log(`[DestinationResolver] [App Discovery] Searching for application "${primaryCandidate}"...`);

  // 1. Check Desktop Shortcuts
  const desktopIcons = await getDesktopIcons();
  const matchedIcon = findDesktopIconMatch(candidates, desktopIcons);

  if (matchedIcon) {
    const iconDipX = Math.round(matchedIcon.X / scaleFactor);
    const iconDipY = Math.round(matchedIcon.Y / scaleFactor);

    const winW = 196;
    const winH = 200;
    let destX = iconDipX + 50;
    if (destX + winW > workArea.x + workArea.width) {
      destX = Math.max(workArea.x, iconDipX - winW);
    }
    destX = Math.max(workArea.x, Math.min(destX, workArea.x + workArea.width - winW));

    let destY = Math.max(workArea.y, Math.min(iconDipY - 20, workArea.y + workArea.height - winH));

    const targetName = matchedIcon.CleanName || matchedIcon.Name;
    console.log(`[DestinationResolver] [App Discovery] Found Desktop shortcut for "${targetName}" at (${iconDipX}, ${iconDipY})`);

    const procName = matchedIcon.IsLnk
      ? `${targetName}.exe`
      : path.basename(matchedIcon.Path);

    const resolvedProcessNames = getCanonicalProcessNames(targetName, [
      procName,
      `${primaryCandidate}.exe`,
      matchedIcon.Path ? path.basename(matchedIcon.Path) : '',
    ]);

    return {
      found: true,
      case: 1,
      status: 'resolved',
      discoveryType: 'application',
      foundOnDesktop: true,
      hasDesktopShortcut: true,
      targetName,
      targetPath: matchedIcon.Path,
      isFolder: matchedIcon.IsFolder,
      isLnk: matchedIcon.IsLnk,
      destination: { x: destX, y: destY },
      iconCoordinates: { x: iconDipX, y: iconDipY },
      launchType: matchedIcon.IsLnk ? 'shortcut' : (matchedIcon.IsFolder ? 'folder' : 'executable'),
      launchTarget: matchedIcon.Path,
      processNames: resolvedProcessNames,
      explanation: `${targetName} found on Windows Desktop at coordinate (${iconDipX}, ${iconDipY}).`,
    };
  }

  // 2 - 6. Search Installed Windows Applications (Start Menu, App Paths, PATH, Packaged Apps, Registry)
  for (const candidate of candidates) {
    const appResult = await searchInstalledApplication(candidate);
    if (appResult && appResult.Found) {
      const targetName = appResult.DisplayName || candidate;

      // When no Desktop shortcut exists, navigate visibly via the Start / Application Launcher route
      // Position Doraemon above the Windows Taskbar Start zone
      const startLauncherX = Math.max(workArea.x + 80, 80);
      const startLauncherY = Math.max(workArea.y + 100, workArea.y + workArea.height - 200);

      console.log(`[DestinationResolver] [App Discovery] Found installed application: "${targetName}" via ${appResult.SourceDescription}`);

      const resolvedProcessNames = getCanonicalProcessNames(
        targetName,
        appResult.ProcessNames || [`${targetName}.exe`, `${candidate}.exe`]
      );

      return {
        found: true,
        case: 2,
        status: 'resolved',
        discoveryType: 'application',
        foundOnDesktop: false,
        hasDesktopShortcut: false,
        requiresStartSearch: true,
        targetName,
        targetPath: appResult.Path || appResult.LaunchTarget,
        destination: { x: startLauncherX, y: startLauncherY },
        navigationRoute: 'start_search',
        launchType: appResult.LaunchType,
        launchTarget: appResult.LaunchTarget,
        appUserModelId: appResult.AppUserModelId,
        processNames: resolvedProcessNames,
        explanation: `${targetName} found in installed Windows applications (${appResult.SourceDescription || 'Start Menu/App Paths'}).`,
      };
    }
  }

  console.log(`[DestinationResolver] [App Discovery] Application "${primaryCandidate}" not found in installed applications.`);
  return {
    found: false,
    status: 'not_found',
    discoveryType: 'application',
    targetName: primaryCandidate,
    explanation: `Could not find "${primaryCandidate}" in installed Windows applications or on Desktop.`,
  };
}

/**
 * ─────────────────────────────────────────────────────────────────────────────
 * DISCOVERY SYSTEM B: File and Folder Discovery
 * ─────────────────────────────────────────────────────────────────────────────
 * Priority search order:
 * 1. Check Windows Desktop.
 * 2. Search known folders & indexed locations (Downloads, Documents, Pictures, etc.).
 * 3. Fallback to File Explorer / Windows search.
 * 4. Multi-match clarification if multiple results exist.
 *
 * @param {string} rawCommand
 * @param {object} displayInfo
 * @param {string} [specificPathChoice]
 * @returns {Promise<object>}
 */
async function discoverFileOrFolder(rawCommand, displayInfo = {}, specificPathChoice = null) {
  const workArea = displayInfo.workArea || { x: 0, y: 0, width: 1536, height: 816 };
  const scaleFactor = displayInfo.scaleFactor || 1.0;

  // If user selected a clarified path
  if (specificPathChoice) {
    console.log(`[DestinationResolver] [File Discovery] User clarified path choice: ${specificPathChoice}`);
    exec(`cmd.exe /c start "" explorer.exe /select,"${specificPathChoice}"`);
    await new Promise((r) => setTimeout(r, 600));

    const winBounds = await getExplorerWindowBounds(specificPathChoice);
    const winDipX = Math.round(winBounds.left / scaleFactor);
    const winDipY = Math.round(winBounds.top / scaleFactor);

    const winW = 196;
    const winH = 200;
    let destX = Math.max(workArea.x, Math.min(winDipX + 50, workArea.x + workArea.width - winW));
    let destY = Math.max(workArea.y, Math.min(winDipY + 30, workArea.y + workArea.height - winH));

    const fileName = path.basename(specificPathChoice);
    return {
      found: true,
      case: 2,
      status: 'resolved',
      discoveryType: 'file_or_folder',
      foundOnDesktop: false,
      targetName: fileName,
      targetPath: specificPathChoice,
      isFolder: !path.extname(specificPathChoice),
      destination: { x: destX, y: destY },
      searchWindowCoordinates: { x: winDipX, y: winDipY },
      explanation: `Selected "${fileName}" at "${specificPathChoice}". Moving Doraemon to File Explorer window.`,
    };
  }

  const candidates = extractTargetCandidates(rawCommand);
  const primaryCandidate = candidates[0] || rawCommand.trim();

  console.log(`[DestinationResolver] [File Discovery] Searching for file/folder "${primaryCandidate}"...`);

  // 1. Check Windows Desktop
  const desktopIcons = await getDesktopIcons();
  const matchedIcon = findDesktopIconMatch(candidates, desktopIcons);

  if (matchedIcon) {
    const iconDipX = Math.round(matchedIcon.X / scaleFactor);
    const iconDipY = Math.round(matchedIcon.Y / scaleFactor);

    const winW = 196;
    const winH = 200;
    let destX = iconDipX + 50;
    if (destX + winW > workArea.x + workArea.width) {
      destX = Math.max(workArea.x, iconDipX - winW);
    }
    destX = Math.max(workArea.x, Math.min(destX, workArea.x + workArea.width - winW));

    let destY = Math.max(workArea.y, Math.min(iconDipY - 20, workArea.y + workArea.height - winH));

    const targetName = matchedIcon.CleanName || matchedIcon.Name;
    console.log(`[DestinationResolver] [File Discovery] Found "${targetName}" on Desktop at (${iconDipX}, ${iconDipY})`);

    return {
      found: true,
      case: 1,
      status: 'resolved',
      discoveryType: 'file_or_folder',
      foundOnDesktop: true,
      targetName,
      targetPath: matchedIcon.Path,
      isFolder: matchedIcon.IsFolder,
      isLnk: matchedIcon.IsLnk,
      iconCoordinates: { x: iconDipX, y: iconDipY },
      destination: { x: destX, y: destY },
      explanation: `Found "${matchedIcon.Name}" directly on Windows Desktop at coordinate (${iconDipX}, ${iconDipY}).`,
    };
  }

  // 2. Search User Directories & Indexed Locations
  console.log(`[DestinationResolver] [File Discovery] Target not on Desktop. Searching system folders for "${primaryCandidate}"...`);
  const searchResults = await searchSystemFiles(primaryCandidate);

  if (searchResults.length === 0) {
    return {
      found: false,
      case: 2,
      status: 'not_found',
      discoveryType: 'file_or_folder',
      targetName: primaryCandidate,
      explanation: `Could not locate "${primaryCandidate}" on the Windows Desktop or in system folders.`,
    };
  }

  if (searchResults.length > 1) {
    return {
      found: false,
      case: 2,
      status: 'clarification_required',
      discoveryType: 'file_or_folder',
      targetName: primaryCandidate,
      matches: searchResults.slice(0, 5),
      explanation: `Found ${searchResults.length} matching locations for "${primaryCandidate}". Clarification required.`,
    };
  }

  // Exactly 1 match found
  const singleMatch = searchResults[0];
  console.log(`[DestinationResolver] [File Discovery] Single system search match: ${singleMatch.path}`);

  if (singleMatch.isFolder) {
    exec(`cmd.exe /c start "" explorer.exe "${singleMatch.path}"`);
  } else {
    exec(`cmd.exe /c start "" explorer.exe /select,"${singleMatch.path}"`);
  }
  await new Promise((r) => setTimeout(r, 600));

  const winBounds = await getExplorerWindowBounds(singleMatch.path);
  const winDipX = Math.round(winBounds.left / scaleFactor);
  const winDipY = Math.round(winBounds.top / scaleFactor);

  const winW = 196;
  const winH = 200;
  let destX = Math.max(workArea.x, Math.min(winDipX + 50, workArea.x + workArea.width - winW));
  let destY = Math.max(workArea.y, Math.min(winDipY + 30, workArea.y + workArea.height - winH));

  return {
    found: true,
    case: 2,
    status: 'resolved',
    discoveryType: 'file_or_folder',
    foundOnDesktop: false,
    targetName: singleMatch.name,
    targetPath: singleMatch.path,
    isFolder: singleMatch.isFolder,
    destination: { x: destX, y: destY },
    searchWindowCoordinates: { x: winDipX, y: winDipY },
    explanation: `Found "${singleMatch.name}" at "${singleMatch.path}". Moving Doraemon to File Explorer window.`,
  };
}

/**
 * ─────────────────────────────────────────────────────────────────────────────
 * UNIFIED TARGET RESOLVER
 * ─────────────────────────────────────────────────────────────────────────────
 * Accurately routes to Application Discovery or File/Folder Discovery.
 *
 * @param {string} rawCommand
 * @param {object} displayInfo
 * @param {string} [specificPathChoice]
 * @param {'auto' | 'application' | 'file_or_folder'} [targetKind='auto']
 * @returns {Promise<object>}
 */
async function resolveDestination(rawCommand, displayInfo = {}, specificPathChoice = null, targetKind = 'auto') {
  if (specificPathChoice) {
    return await discoverFileOrFolder(rawCommand, displayInfo, specificPathChoice);
  }

  const clean = (rawCommand || '').trim();
  const isExplorerApp = /\b(?:file\s+explorer|explorer|my\s+computer|file\s+manager)\b/i.test(clean);
  const isExplicitFileOrFolder = !isExplorerApp && /\b(folder|directory|dir|file|document|pdf|txt|png|jpg|mp4|zip)\b/i.test(clean);
  const isExplicitApp = isExplorerApp || /\b(app|application|program|software|tool|calc|calculator|notepad|chrome|code|vscode|whatsapp|spotify|netflix|browser)\b/i.test(clean);

  // 1. Explicitly requested as application
  if (targetKind === 'application') {
    return await discoverApplication(clean, displayInfo);
  }

  // 2. Explicitly requested as file or folder
  if (targetKind === 'file_or_folder') {
    return await discoverFileOrFolder(clean, displayInfo);
  }

  // 3. Auto mode: if clearly phrased as an application
  if (isExplicitApp && !isExplicitFileOrFolder) {
    return await discoverApplication(clean, displayInfo);
  }

  // 4. Auto mode: if clearly phrased as a file/folder
  if (isExplicitFileOrFolder && !isExplicitApp) {
    return await discoverFileOrFolder(clean, displayInfo);
  }

  // Auto mode: check Application discovery first
  const appResult = await discoverApplication(clean, displayInfo);
  if (appResult && appResult.found) {
    return appResult;
  }

  // If not found as an application, check File and Folder discovery
  const fileResult = await discoverFileOrFolder(clean, displayInfo);
  if (fileResult && (fileResult.found || fileResult.status === 'clarification_required')) {
    return fileResult;
  }

  // If neither found, report truthful not_found
  return {
    found: false,
    status: 'not_found',
    targetName: clean,
    explanation: `Could not find "${clean}" in installed Windows applications, Desktop shortcuts, or system folders.`,
  };
}

module.exports = {
  resolveDestination,
  discoverApplication,
  discoverFileOrFolder,
  getDesktopIcons,
  searchSystemFiles,
  searchInstalledApplication,
  extractTargetCandidates,
  getStartButtonCoordinates,
  openStartAndGetSearchBox,
  searchAndGetResultCoordinates,
  closeStartMenu,
  CANONICAL_APP_PROCESSES,
  getCanonicalProcessNames,
};
