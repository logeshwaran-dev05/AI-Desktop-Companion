/**
 * App Launch & Desktop Task State Machine
 * ========================================
 * Implements the official task states and multi-stage lifecycle required for real
 * Windows companion operations:
 *
 * Task Lifecycle Stages:
 *   1. request_received  (15%) → Request acknowledged and queued.
 *   2. understanding     (35%) → AI parsing intent and locating shortcut coordinates.
 *   3. validating        (55%) → Verifying against allowlist registry and permissions.
 *   4. waiting_execution (70%) → Preparing desktop companion window and movement path.
 *   5. launch_attempted  (85%) → ShellExecute invoked; waiting for process detection.
 *   6. launch_verified   (100%)→ Process confirmed running in Windows tasklist.
 *   -  failed                  → Honest error explanation; Doraemon displays error badge.
 *   -  cancelled               → User or system stopped action; safely returned home.
 */

export type TaskState =
  | 'idle'
  | 'planning'
  | 'awaiting_approval'
  | 'launching'
  | 'success'
  | 'failed'
  | 'cancelled'

export type LaunchState =
  | TaskState
  | 'not-in-electron'
  | 'not-allowed'
  | 'running'
  | 'resolving'
  | 'error'

export type ExecutionMode = 'real' | 'mock'

export type TaskStageId =
  | 'request_received'
  | 'understanding'
  | 'validating'
  | 'waiting_execution'
  | 'launch_attempted'
  | 'launch_verified'
  | 'failed'
  | 'cancelled'

export interface TaskStage {
  id: TaskStageId
  label: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled'
  timestamp?: string
  detail?: string
}

export interface LiveTaskProgress {
  taskId: string
  rawCommand: string
  currentStageId: TaskStageId
  percent: number
  stages: TaskStage[]
  displayName?: string
  appId?: string
  isVerified?: boolean
  error?: string
  executionMode: ExecutionMode
}

export interface TargetInfo {
  foundShortcut: boolean
  shortcutPath: string | null
  destination: { x: number; y: number }
  destinationType: 'desktop-shortcut' | 'taskbar-fallback' | 'grid-fallback'
  explanation: string
}

/**
 * A snapshot of the result of a launch attempt, stored on Message and Task
 * records so that the UI can show persistent banners.
 */
export interface LaunchResult {
  /** The terminal launch state this result represents */
  state: LaunchState
  taskState?: TaskState
  /** Human-readable app name, e.g. "Notepad" */
  displayName: string
  /** Allowlist app id, e.g. "notepad" */
  appId: string
  /**
   * true only when a real Electron IPC call was made.
   * false in browser-mode or not-allowed paths (never fakes success).
   */
  realLaunch: boolean
  /**
   * true only if the IPC call confirms the process started in tasklist.
   */
  verified?: boolean
  /** Error description, present on error / not-allowed / not-in-electron states */
  errorMessage?: string
  /** Discovered target details and desktop coordinate destination */
  targetInfo?: TargetInfo
  /** Execution mode: 'real' | 'mock' */
  executionMode?: ExecutionMode
  /** Clearly marks simulated events in Mock mode */
  mockSimulated?: boolean
  cancelled?: boolean
}

/** Allowlist of recognizable phrases → app identifier */
const PHRASE_MAP: Array<{ patterns: RegExp[]; appId: string; displayName: string }> = [
  {
    patterns: [/notepad/i],
    appId: 'notepad',
    displayName: 'Notepad',
  },
  {
    patterns: [/calc(ulator)?/i],
    appId: 'calculator',
    displayName: 'Calculator',
  },
  {
    patterns: [/file\s*explorer|explorer|my\s*computer|file\s*manager/i],
    appId: 'explorer',
    displayName: 'File Explorer',
  },
  {
    patterns: [/chrome|google\s*chrome|browser/i],
    appId: 'chrome',
    displayName: 'Google Chrome',
  },
  {
    patterns: [/vs\s*code|vscode|visual\s*studio\s*code|code/i],
    appId: 'vscode',
    displayName: 'Visual Studio Code',
  },
  {
    patterns: [/whats\s*app|whatsapp/i],
    appId: 'whatsapp',
    displayName: 'WhatsApp',
  },
]

/**
 * Creates the initial multi-stage task progress model.
 */
export function createInitialTaskProgress(
  taskId: string,
  rawCommand: string,
  mode: ExecutionMode
): LiveTaskProgress {
  const timeNow = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  return {
    taskId,
    rawCommand,
    currentStageId: 'request_received',
    percent: 15,
    executionMode: mode,
    stages: [
      {
        id: 'request_received',
        label: 'Request received',
        status: 'completed',
        timestamp: timeNow,
        detail: `Received command: "${rawCommand}"`,
      },
      {
        id: 'understanding',
        label: 'Understanding request',
        status: 'in_progress',
        detail: 'Analyzing natural language intent…',
      },
      {
        id: 'validating',
        label: 'Validating application',
        status: 'pending',
        detail: 'Checking allowlist and discovering shortcut path…',
      },
      {
        id: 'waiting_execution',
        label: 'Waiting for execution',
        status: 'pending',
        detail: 'Synchronizing desktop companion window…',
      },
      {
        id: 'launch_attempted',
        label: 'Launch attempted',
        status: 'pending',
        detail: 'Invoking Windows process launcher…',
      },
      {
        id: 'launch_verified',
        label: 'Launch verified',
        status: 'pending',
        detail: 'Awaiting process verification in tasklist…',
      },
    ],
  }
}

/**
 * Resolve a natural-language command string to a known app identifier.
 * Returns null if no known app is found in the text.
 */
export function resolveAppIntent(text: string): { appId: string; displayName: string } | null {
  for (const entry of PHRASE_MAP) {
    for (const pattern of entry.patterns) {
      if (pattern.test(text)) {
        return { appId: entry.appId, displayName: entry.displayName }
      }
    }
  }
  return null
}

/** Check whether the text looks like a "launch / open application" intent */
export function isLaunchIntent(text: string): boolean {
  if (/\b(open|launch|start|run|show|access)\b/i.test(text)) return true
  return resolveAppIntent(text) !== null
}
