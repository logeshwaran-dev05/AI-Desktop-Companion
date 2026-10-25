export interface CompanionAPI {
  openDashboard: () => Promise<boolean>;
  closeDashboard: () => Promise<boolean>;
  sleepAvatar: () => Promise<boolean>;
  wakeAvatar: () => Promise<boolean>;
  quitApp: () => Promise<void>;
  onSyncState: (callback: (data: { avatarState?: string; isSleeping?: boolean }) => void) => () => void;
  sendSyncState: (data: { avatarState?: string; isSleeping?: boolean }) => Promise<boolean>;
  moveAvatar?: (deltaX: number, deltaY: number) => Promise<boolean>;
  isElectron: boolean;
}

declare global {
  interface Window {
    companionAPI?: CompanionAPI;
  }
}
