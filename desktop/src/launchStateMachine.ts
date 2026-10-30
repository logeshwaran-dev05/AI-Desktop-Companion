/**
 * App Launch & Desktop Task State Machine
 * ========================================
 * Implements the official task states required for real Windows companion operations:
 *   idle              → Doraemon stands at home position.
 *   planning          → Resolving intent and locating shortcut / desktop coordinates.
 *   awaiting_approval → Waiting for user approval (when configured).
 *   launching         → Doraemon visibly travels across the desktop toward target.
 *   success           → Verified process launch; celebration at destination.
 *   failed            → Error handled; Doraemon stops and displays real explanation.
 *   cancelled         → User cancelled; safe stop and return home.
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
   * true only if the IPC call confirms the process started.
   * Always false — we cannot verify GUI window visibility from the main process.
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
  return /\b(open|launch|start|run|show)\b/i.test(text)
}
