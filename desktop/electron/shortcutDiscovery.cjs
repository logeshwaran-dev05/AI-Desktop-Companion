
/**
 * WINDOWS DESKTOP SHORTCUT DISCOVERY SERVICE
 * ============================================
 * Discovers Windows shortcuts (.lnk) on the user's desktop, public desktop,
 * and Start Menu without executing arbitrary contents.
 *
 * Provides resolved desktop screen coordinates for Doraemon to travel toward.
 * When a shortcut is not present on the desktop, calculates a well-defined fallback
 * location (e.g. Windows Taskbar / Start launcher zone or application grid zone).
 */

const fs = require('fs');
const path = require('path');
const { screen } = require('electron');

/**
 * Known applications and their typical shortcut names and desktop grid preferences
 */
const APP_SHORTCUT_REGISTRY = {
  notepad: {
    displayName: 'Notepad',
    possibleShortcuts: ['Notepad.lnk'],
    defaultZone: 'taskbar-start', // Built-in Windows app -> Taskbar/Start zone
    gridIndex: 0,
  },
  calculator: {
    displayName: 'Calculator',
    possibleShortcuts: ['Calculator.lnk'],
    defaultZone: 'taskbar-tools',
    gridIndex: 1,
  },
  explorer: {
    displayName: 'File Explorer',
    possibleShortcuts: ['File Explorer.lnk', 'Windows Explorer.lnk'],
    defaultZone: 'taskbar-tools',
    gridIndex: 2,
  },
  chrome: {
    displayName: 'Google Chrome',
    possibleShortcuts: ['Google Chrome.lnk', 'Chrome.lnk'],
    defaultZone: 'desktop-grid',
    gridIndex: 3,
  },
  vscode: {
    displayName: 'Visual Studio Code',
    possibleShortcuts: ['Visual Studio Code.lnk', 'Code.lnk'],
    defaultZone: 'desktop-grid',
    gridIndex: 4,
  },
  whatsapp: {
    displayName: 'WhatsApp',
    possibleShortcuts: ['WhatsApp.lnk', 'WhatsApp Desktop.lnk'],
    defaultZone: 'desktop-grid',
    gridIndex: 5,
  },
};

/**
 * Searches Desktop directories for an existing .lnk file
 * @param {string[]} possibleNames
 * @returns {string|null} Full path to shortcut if found
 */
function findDesktopShortcut(possibleNames) {
  const userDesktop = path.join(process.env.USERPROFILE || '', 'Desktop');
  const publicDesktop = path.join(process.env.PUBLIC || 'C:\\Users\\Public', 'Desktop');

  const searchDirs = [userDesktop, publicDesktop];

  for (const dir of searchDirs) {
    if (!dir || !fs.existsSync(dir)) continue;
    for (const name of possibleNames) {
      const fullPath = path.join(dir, name);
      if (fs.existsSync(fullPath)) {
        return fullPath;
      }
    }
  }

  return null;
}

/**
 * Resolves the screen coordinate destination for Doraemon.
 *
 * @param {string} appId - Normalized app identifier ('notepad', 'calculator', etc.)
 * @returns {{
 *   foundShortcut: boolean,
 *   shortcutPath: string | null,
 *   destination: { x: number, y: number },
 *   destinationType: 'desktop-shortcut' | 'taskbar-fallback' | 'grid-fallback',
 *   explanation: string
 * }}
 */
function resolveAppTarget(appId) {
  const normId = (appId || '').trim().toLowerCase();
  const config = APP_SHORTCUT_REGISTRY[normId] || {
    displayName: appId,
    possibleShortcuts: [`${appId}.lnk`],
    defaultZone: 'desktop-grid',
    gridIndex: 5,
  };

  const primaryDisplay = screen.getPrimaryDisplay();
  const workArea = primaryDisplay.workArea;

  const shortcutPath = findDesktopShortcut(config.possibleShortcuts);

  if (shortcutPath) {
    // Standard Windows Desktop Icon Grid: Left column, spaced 75px wide by 90px tall
    // Icons typically begin around x: 40, y: 40 + (index * 95)
    const iconX = Math.max(workArea.x + 40, 40);
    const iconY = Math.min(
      workArea.y + 60 + config.gridIndex * 95,
      workArea.y + workArea.height - 220
    );

    return {
      foundShortcut: true,
      shortcutPath,
      destination: { x: iconX, y: iconY },
      destinationType: 'desktop-shortcut',
      explanation: `Found desktop shortcut at "${shortcutPath}". Traveling to desktop icon location (${iconX}, ${iconY}).`,
    };
  }

  // Fallback Destination: Clearly defined and documented
  if (config.defaultZone === 'taskbar-start' || config.defaultZone === 'taskbar-tools') {
    // Windows Taskbar launch zone at bottom-left
    const taskbarX = Math.max(workArea.x + 50 + config.gridIndex * 60, 50);
    const taskbarY = Math.max(workArea.y + workArea.height - 240, 100);

    return {
      foundShortcut: false,
      shortcutPath: null,
      destination: { x: taskbarX, y: taskbarY },
      destinationType: 'taskbar-fallback',
      explanation: `No desktop shortcut found for ${config.displayName}. Navigating to Windows Start/Taskbar launcher zone (${taskbarX}, ${taskbarY}).`,
    };
  }

  // Fallback to desktop application grid zone
  const fallbackX = Math.max(workArea.x + 80, 80);
  const fallbackY = Math.max(workArea.y + 80 + (config.gridIndex % 4) * 110, 80);

  return {
    foundShortcut: false,
    shortcutPath: null,
    destination: { x: fallbackX, y: fallbackY },
    destinationType: 'grid-fallback',
    explanation: `No desktop shortcut found for ${config.displayName}. Traveling to primary desktop grid location (${fallbackX}, ${fallbackY}).`,
  };
}

module.exports = {
  resolveAppTarget,
  APP_SHORTCUT_REGISTRY,
};

