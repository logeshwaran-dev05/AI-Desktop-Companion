/** Shape returned by the Electron main process companion:launch-app IPC handler */
export interface IpcLaunchResult {
  success: boolean;
  /** Always false — we cannot verify GUI window visibility from main process */
  verified: boolean;
  displayName: string;
  mode: 'real' | 'not-found' | 'not-allowed' | 'mock';
  error?: string;
  mockSimulated?: boolean;
  message?: string;
}

export interface TargetInfo {
  foundShortcut: boolean;
  shortcutPath: string | null;
  destination: { x: number; y: number };
  destinationType: 'desktop-shortcut' | 'taskbar-fallback' | 'grid-fallback';
  explanation: string;
}

export interface DesktopTaskResult extends IpcLaunchResult {
  taskState: 'success' | 'failed' | 'cancelled';
  targetInfo?: TargetInfo;
  executionMode: 'real' | 'mock';
  cancelled?: boolean;
}

export interface MovementStep {
  currentX: number;
  currentY: number;
  progress: number;
  facing: 'left' | 'right';
}

export interface CompanionSyncData {
  avatarState?: string;
  isSleeping?: boolean;
  facing?: 'left' | 'right';
  taskState?: string;
  isMoving?: boolean;
  chatboxOpen?: boolean;
}

export interface UpdateInfo {
  updateAvailable: boolean;
  currentVersion: string;
  remoteVersion?: string;
  releaseNotes?: string;
  downloadUrl?: string;
  setupExeUrl?: string;
  manualUrl?: string;
  error?: string;
}

export interface UpdateApplyResult {
  success: boolean;
  newVersion?: string;
  error?: string;
  manualUrl?: string;
}

export interface CompanionAPI {
  openDashboard: () => Promise<boolean>;
  closeDashboard: () => Promise<boolean>;
  sleepAvatar: () => Promise<boolean>;
  wakeAvatar: () => Promise<boolean>;
  quitApp: () => Promise<void>;
  onSyncState: (callback: (data: CompanionSyncData) => void) => () => void;
  sendSyncState: (data: CompanionSyncData) => Promise<boolean>;
  moveAvatar?: (deltaX: number, deltaY: number) => Promise<boolean>;
  launchApp: (appId: string, options?: { query?: string }) => Promise<IpcLaunchResult>;

  startDesktopTask: (data: { appId: string; displayName: string; query?: string }) => Promise<DesktopTaskResult>;
  cancelMovement: () => Promise<boolean>;
  returnHome: () => Promise<boolean>;
  setExecutionMode: (mode: 'real' | 'mock') => Promise<'real' | 'mock'>;
  getExecutionMode: () => Promise<'real' | 'mock'>;
  triggerVoiceTyping?: () => Promise<boolean>;
  setChatboxOpen?: (isOpen: boolean) => Promise<boolean>;

  onTaskProgress: (callback: (data: any) => void) => () => void;
  onMovementProgress: (callback: (data: MovementStep) => void) => () => void;

  checkUpdates?: () => Promise<UpdateInfo>;
  applyUpdate?: (updateInfo: UpdateInfo) => Promise<UpdateApplyResult>;
  openExternal?: (url?: string) => Promise<boolean>;
  getCurrentVersion?: () => Promise<string>;
  relaunchApp?: () => Promise<void>;
  onUpdateAvailable?: (callback: (info: UpdateInfo) => void) => () => void;
  onUpdateCompleted?: (callback: (res: UpdateApplyResult) => void) => () => void;

  isElectron: boolean;
}

declare global {
  interface Window {
    companionAPI?: CompanionAPI;
  }
}
