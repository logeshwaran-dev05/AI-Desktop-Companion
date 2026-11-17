/**
 * DESKTOP MOVEMENT CONTROLLER
 * =============================
 * Smoothly moves the transparent Doraemon BrowserWindow across the visible
 * Windows desktop toward a destination coordinate.
 *
 * Ensures:
 * - 60 FPS incremental coordinate updates using ease-in-out interpolation.
 * - Directional awareness: updates Doraemon's facing ('left' | 'right').
 * - Focus preservation: never steals keyboard focus from the active app.
 * - Screen boundary clamping within the current display work area.
 * - Cancellation support: safe stop at any point.
 */

const { screen } = require('electron');

let activeMovement = null;
let homePosition = null;

/**
 * Calculates cubic ease-in-out interpolation factor
 * @param {number} t - Progress between 0 and 1
 * @returns {number}
 */
function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

/**
 * Initializes or retrieves Doraemon's home base coordinates
 * @param {import('electron').BrowserWindow} window
 * @returns {{ x: number, y: number }}
 */
function getHomePosition(window) {
  if (homePosition) return homePosition;

  const primaryDisplay = screen.getPrimaryDisplay();
  const workArea = primaryDisplay.workArea;
  const [width, height] = window.getSize();

  homePosition = {
    x: Math.max(0, Math.round(workArea.x + workArea.width - width - 24)),
    y: Math.max(0, Math.round(workArea.y + workArea.height - height - 24)),
  };

  return homePosition;
}

/**
 * Stops any currently active movement animation safely
 */
function cancelActiveMovement() {
  if (activeMovement) {
    if (activeMovement.timer) {
      clearInterval(activeMovement.timer);
    }
    activeMovement.cancelled = true;
    activeMovement = null;
  }
}

/**
 * Smoothly travels Doraemon from his current desktop position to (targetX, targetY).
 *
 * @param {import('electron').BrowserWindow} avatarWindow
 * @param {number} targetX
 * @param {number} targetY
 * @param {object} options
 * @param {number} [options.durationMs=2000] - Duration of travel in milliseconds
 * @param {function} [options.onStep] - Called on each coordinate step with { currentX, currentY, progress, facing }
 * @returns {Promise<{ completed: boolean, cancelled: boolean, finalPos: { x: number, y: number } }>}
 */
function moveAvatarTo(avatarWindow, targetX, targetY, options = {}) {
  return new Promise((resolve) => {
    if (!avatarWindow || avatarWindow.isDestroyed()) {
      resolve({ completed: false, cancelled: true, finalPos: { x: targetX, y: targetY } });
      return;
    }

    // Cancel any running movement
    cancelActiveMovement();

    const [startX, startY] = avatarWindow.getPosition();
    const primaryDisplay = screen.getDisplayNearestPoint({ x: startX, y: startY });
    const workArea = primaryDisplay.workArea;
    const [winWidth, winHeight] = avatarWindow.getSize();

    // Clamp destination to visible desktop boundaries
    const clampedTargetX = Math.max(workArea.x, Math.min(targetX, workArea.x + workArea.width - winWidth));
    const clampedTargetY = Math.max(workArea.y, Math.min(targetY, workArea.y + workArea.height - winHeight));

    const deltaX = clampedTargetX - startX;
    const deltaY = clampedTargetY - startY;
    const distance = Math.hypot(deltaX, deltaY);

    if (distance < 5) {
      avatarWindow.setPosition(clampedTargetX, clampedTargetY);
      resolve({ completed: true, cancelled: false, finalPos: { x: clampedTargetX, y: clampedTargetY } });
      return;
    }

    // Derive facing direction from horizontal travel
    const facing = deltaX < 0 ? 'left' : 'right';

    // Calculate duration based on distance (minimum 2400ms, maximum 3800ms for smooth pacing)
    const duration = options.durationMs || Math.min(3800, Math.max(2400, Math.round(distance * 3.2)));
    const frameRateMs = 16; // ~60fps
    const totalSteps = Math.max(1, Math.round(duration / frameRateMs));

    let currentStep = 0;

    const movementRecord = {
      cancelled: false,
      timer: null,
    };

    activeMovement = movementRecord;

    // Notify avatar window of initial motion and facing direction
    if (!avatarWindow.isDestroyed() && avatarWindow.webContents) {
      avatarWindow.webContents.send('companion:sync-state', {
        avatarState: 'Working',
        facing,
        isMoving: true,
        taskState: 'launching',
      });
    }

    movementRecord.timer = setInterval(() => {
      if (movementRecord.cancelled || avatarWindow.isDestroyed()) {
        clearInterval(movementRecord.timer);
        resolve({ completed: false, cancelled: true, finalPos: avatarWindow.isDestroyed() ? { x: 0, y: 0 } : { x: avatarWindow.getPosition()[0], y: avatarWindow.getPosition()[1] } });
        return;
      }

      currentStep++;
      const progress = Math.min(1, currentStep / totalSteps);
      const easedProgress = easeInOutCubic(progress);

      const nextX = Math.round(startX + deltaX * easedProgress);
      const nextY = Math.round(startY + deltaY * easedProgress);

      // setPosition on transparent window (avoid stealing focus)
      avatarWindow.setPosition(nextX, nextY);

      if (options.onStep) {
        options.onStep({
          currentX: nextX,
          currentY: nextY,
          progress,
          facing,
        });
      }

      if (progress >= 1) {
        clearInterval(movementRecord.timer);
        activeMovement = null;

        // Final arrival notification
        if (!avatarWindow.isDestroyed() && avatarWindow.webContents) {
          avatarWindow.webContents.send('companion:sync-state', {
            avatarState: 'Success',
            facing,
            isMoving: false,
            taskState: 'success',
          });
        }

        resolve({
          completed: true,
          cancelled: false,
          finalPos: { x: nextX, y: nextY },
        });
      }
    }, frameRateMs);
  });
}

/**
 * Returns Doraemon to his home position in the bottom-right corner of the desktop
 * @param {import('electron').BrowserWindow} avatarWindow
 * @returns {Promise<boolean>}
 */
async function returnHome(avatarWindow) {
  if (!avatarWindow || avatarWindow.isDestroyed()) return false;
  const home = getHomePosition(avatarWindow);
  const result = await moveAvatarTo(avatarWindow, home.x, home.y, { durationMs: 2600 });
  return result.completed;
}

/**
 * Positions Doraemon directly docked or hanging right above the Windows taskbar.
 * In Windows, `workArea` automatically subtracts the taskbar height,
 * so `workArea.y + workArea.height - winHeight` places Doraemon's feet precisely on the taskbar.
 *
 * @param {import('electron').BrowserWindow} avatarWindow
 * @param {number} [horizontalRatio=0.85] - Position across screen (0.0 = left edge, 1.0 = right edge)
 * @returns {Promise<boolean>}
 */
async function dockToTaskbar(avatarWindow, horizontalRatio = 0.85) {
  if (!avatarWindow || avatarWindow.isDestroyed()) return false;
  const primaryDisplay = screen.getPrimaryDisplay();
  const workArea = primaryDisplay.workArea;
  const [winWidth, winHeight] = avatarWindow.getSize();

  const targetX = Math.round(workArea.x + (workArea.width - winWidth) * Math.max(0, Math.min(1, horizontalRatio)));
  // Sit directly on the taskbar boundary
  const targetY = Math.round(workArea.y + workArea.height - winHeight);

  const result = await moveAvatarTo(avatarWindow, targetX, targetY, { durationMs: 2000 });
  return result.completed;
}

/**
 * Animates Doraemon walking along the top of the Windows taskbar
 * @param {import('electron').BrowserWindow} avatarWindow
 * @param {number} fromRatio
 * @param {number} toRatio
 * @param {number} durationMs
 * @returns {Promise<boolean>}
 */
async function walkAlongTaskbar(avatarWindow, fromRatio = 0.85, toRatio = 0.35, durationMs = 3500) {
  if (!avatarWindow || avatarWindow.isDestroyed()) return false;
  const primaryDisplay = screen.getPrimaryDisplay();
  const workArea = primaryDisplay.workArea;
  const [winWidth, winHeight] = avatarWindow.getSize();

  const targetX = Math.round(workArea.x + (workArea.width - winWidth) * toRatio);
  const targetY = Math.round(workArea.y + workArea.height - winHeight);

  const result = await moveAvatarTo(avatarWindow, targetX, targetY, { durationMs });
  return result.completed;
}

module.exports = {
  moveAvatarTo,
  returnHome,
  dockToTaskbar,
  walkAlongTaskbar,
  cancelActiveMovement,
  getHomePosition,
};

