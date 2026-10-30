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
  launchApp: (appId: string) => Promise<IpcLaunchResult>;

  startDesktopTask: (data: { appId: string; displayName: string }) => Promise<DesktopTaskResult>;
  cancelMovement: () => Promise<boolean>;
  returnHome: () => Promise<boolean>;
  setExecutionMode: (mode: 'real' | 'mock') => Promise<'real' | 'mock'>;
  getExecutionMode: () => Promise<'real' | 'mock'>;

  onTaskProgress: (callback: (data: any) => void) => () => void;
  onMovementProgress: (callback: (data: MovementStep) => void) => () => void;

  isElectron: boolean;
}

declare global {
  interface Window {
    companionAPI?: CompanionAPI;
  }
}
