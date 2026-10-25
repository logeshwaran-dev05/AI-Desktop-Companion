const { contextBridge, ipcRenderer } = require('electron');

// Securely expose narrowly scoped companion APIs to renderer
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
});
