const { contextBridge, ipcRenderer } = require('electron');

// Securely expose narrowly scoped companion APIs to renderer.
// nodeIntegration is disabled; contextIsolation is enabled.
// Only explicitly listed channels are bridged.
contextBridge.exposeInMainWorld('companionAPI', {
  openDashboard: () => ipcRenderer.invoke('companion:open-dashboard'),
  closeDashboard: () => ipcRenderer.invoke('companion:close-dashboard'),
  sleepAvatar: () => ipcRenderer.invoke('companion:sleep-avatar'),
  wakeAvatar: () => ipcRenderer.invoke('companion:wake-avatar'),
  quitApp: () => ipcRenderer.invoke('companion:quit-app'),
  onSyncState: (callback) => {
    const subscription = (_event, data) => callback(data);
    ipcRenderer.on('companion:sync-state', subscription);
    return () => ipcRenderer.removeListener('companion:sync-state', subscription);
  },
  sendSyncState: (data) => ipcRenderer.invoke('companion:sync-state', data),
  moveAvatar: (deltaX, deltaY) => ipcRenderer.invoke('companion:move-avatar', { deltaX, deltaY }),
  isElectron: true,

  /**
   * Launch a real Windows application by allowlist identifier.
   */
  launchApp: (appId) => ipcRenderer.invoke('companion:launch-app', appId),

  /**
   * Physical Desktop Movement & Launch Pipeline
   */
  startDesktopTask: (data) => ipcRenderer.invoke('companion:start-desktop-task', data),
  cancelMovement: () => ipcRenderer.invoke('companion:cancel-movement'),
  returnHome: () => ipcRenderer.invoke('companion:return-home'),
  setExecutionMode: (mode) => ipcRenderer.invoke('companion:set-execution-mode', mode),
  getExecutionMode: () => ipcRenderer.invoke('companion:get-execution-mode'),

  onTaskProgress: (callback) => {
    const sub = (_e, data) => callback(data);
    ipcRenderer.on('companion:task-progress', sub);
    return () => ipcRenderer.removeListener('companion:task-progress', sub);
  },
  onMovementProgress: (callback) => {
    const sub = (_e, data) => callback(data);
    ipcRenderer.on('companion:movement-progress', sub);
    return () => ipcRenderer.removeListener('companion:movement-progress', sub);
  },
});
