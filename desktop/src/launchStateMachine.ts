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

export interface ResolvedIntent {
  appId: string
  displayName: string
  query?: string
  actionType: 'open' | 'play' | 'search'
}

/** Allowlist of recognizable phrases → app identifier (Top-50 Apps & Services) */
const PHRASE_MAP: Array<{ patterns: RegExp[]; appId: string; displayName: string }> = [
  // ── Native Windows Utilities ──
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
    patterns: [/chrome|google\s*chrome/i],
    appId: 'chrome',
    displayName: 'Google Chrome',
  },
  {
    patterns: [/edge|microsoft\s*edge/i],
    appId: 'edge',
    displayName: 'Microsoft Edge',
  },
  {
    patterns: [/vs\s*code|vscode|visual\s*studio\s*code|code/i],
    appId: 'vscode',
    displayName: 'Visual Studio Code',
  },
  {
    patterns: [/paint|draw(ing)?|mspaint/i],
    appId: 'paint',
    displayName: 'Paint',
  },
  {
    patterns: [/cmd|command\s*prompt/i],
    appId: 'cmd',
    displayName: 'Command Prompt',
  },
  {
    patterns: [/powershell|pwsh|terminal/i],
    appId: 'terminal',
    displayName: 'Terminal',
  },
  {
    patterns: [/settings|control\s*panel/i],
    appId: 'settings',
    displayName: 'Windows Settings',
  },

  // ── Media & Entertainment ──
  {
    patterns: [/you\s*tube|youtube|yt\b/i],
    appId: 'youtube',
    displayName: 'YouTube',
  },
  {
    patterns: [/spotify/i],
    appId: 'spotify',
    displayName: 'Spotify',
  },
  {
    patterns: [/netflix/i],
    appId: 'netflix',
    displayName: 'Netflix',
  },
  {
    patterns: [/prime\s*video|amazon\s*prime/i],
    appId: 'primevideo',
    displayName: 'Prime Video',
  },
  {
    patterns: [/disney\s*\+?|hotstar/i],
    appId: 'disney',
    displayName: 'Disney+',
  },
  {
    patterns: [/sound\s*cloud/i],
    appId: 'soundcloud',
    displayName: 'SoundCloud',
  },
  {
    patterns: [/twitch/i],
    appId: 'twitch',
    displayName: 'Twitch',
  },

  // ── AI & Assistants ──
  {
    patterns: [/chat\s*gpt|chatgpt|openai/i],
    appId: 'chatgpt',
    displayName: 'ChatGPT',
  },
  {
    patterns: [/claude|anthropic/i],
    appId: 'claude',
    displayName: 'Claude',
  },
  {
    patterns: [/gemini|google\s*bard/i],
    appId: 'gemini',
    displayName: 'Google Gemini',
  },
  {
    patterns: [/copilot|bing\s*chat/i],
    appId: 'copilot',
    displayName: 'Microsoft Copilot',
  },

  // ── Productivity & Cloud ──
  {
    patterns: [/g\s*mail|gmail|google\s*mail/i],
    appId: 'gmail',
    displayName: 'Gmail',
  },
  {
    patterns: [/google\s*drive|g\s*drive|drive/i],
    appId: 'drive',
    displayName: 'Google Drive',
  },
  {
    patterns: [/google\s*docs|docs/i],
    appId: 'docs',
    displayName: 'Google Docs',
  },
  {
    patterns: [/google\s*sheets|sheets/i],
    appId: 'sheets',
    displayName: 'Google Sheets',
  },
  {
    patterns: [/notion/i],
    appId: 'notion',
    displayName: 'Notion',
  },
  {
    patterns: [/slack/i],
    appId: 'slack',
    displayName: 'Slack',
  },
  {
    patterns: [/trello/i],
    appId: 'trello',
    displayName: 'Trello',
  },
  {
    patterns: [/canva/i],
    appId: 'canva',
    displayName: 'Canva',
  },
  {
    patterns: [/maps|google\s*maps|directions/i],
    appId: 'maps',
    displayName: 'Google Maps',
  },
  {
    patterns: [/calendar|google\s*calendar/i],
    appId: 'calendar',
    displayName: 'Google Calendar',
  },

  // ── Developer Platforms ──
  {
    patterns: [/git\s*hub|github/i],
    appId: 'github',
    displayName: 'GitHub',
  },
  {
    patterns: [/git\s*lab|gitlab/i],
    appId: 'gitlab',
    displayName: 'GitLab',
  },
  {
    patterns: [/stack\s*overflow/i],
    appId: 'stackoverflow',
    displayName: 'Stack Overflow',
  },

  // ── Communication & Social ──
  {
    patterns: [/whats\s*app|whatsapp/i],
    appId: 'whatsapp',
    displayName: 'WhatsApp',
  },
  {
    patterns: [/discord/i],
    appId: 'discord',
    displayName: 'Discord',
  },
  {
    patterns: [/telegram/i],
    appId: 'telegram',
    displayName: 'Telegram',
  },
  {
    patterns: [/linkedin/i],
    appId: 'linkedin',
    displayName: 'LinkedIn',
  },
  {
    patterns: [/twitter|\bx\b|tweet/i],
    appId: 'twitter',
    displayName: 'X (Twitter)',
  },
  {
    patterns: [/reddit/i],
    appId: 'reddit',
    displayName: 'Reddit',
  },
  {
    patterns: [/instagram|insta\b/i],
    appId: 'instagram',
    displayName: 'Instagram',
  },
  {
    patterns: [/facebook|fb\b/i],
    appId: 'facebook',
    displayName: 'Facebook',
  },
  {
    patterns: [/google/i],
    appId: 'google',
    displayName: 'Google',
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
 * Resolve a natural-language command string to an application intent,
 * extracting query parameters for YouTube playback, web search, or app execution.
 */
export function resolveAppIntent(rawText: string): ResolvedIntent {
  const text = (rawText || '').trim()
  if (!text) {
    return {
      appId: 'google',
      displayName: 'Google Search',
      query: '',
      actionType: 'search',
    }
  }

  // 1. YouTube playback patterns:
  // e.g. "open youtube and play faded", "play believer on youtube", "play faded"
  const ytPlayMatch1 = text.match(/(?:open|launch|start|go to)?\s*(?:youtube|yt)\s*(?:and|then)?\s*(?:play|stream|listen to)\s+(.+)$/i)
  if (ytPlayMatch1 && ytPlayMatch1[1]?.trim()) {
    return {
      appId: 'youtube',
      displayName: 'YouTube',
      query: ytPlayMatch1[1].trim(),
      actionType: 'play',
    }
  }

  const ytPlayMatch2 = text.match(/(?:play|stream|listen to)\s+(.+?)\s+(?:on|in)\s+(?:youtube|yt)$/i)
  if (ytPlayMatch2 && ytPlayMatch2[1]?.trim()) {
    return {
      appId: 'youtube',
      displayName: 'YouTube',
      query: ytPlayMatch2[1].trim(),
      actionType: 'play',
    }
  }

  // 2. Spotify playback patterns:
  // e.g. "open spotify and play coldplay", "play starboy on spotify"
  const spotifyPlayMatch1 = text.match(/(?:open|launch|start)?\s*spotify\s*(?:and|then)?\s*(?:play|stream|listen to)\s+(.+)$/i)
  if (spotifyPlayMatch1 && spotifyPlayMatch1[1]?.trim()) {
    return {
      appId: 'spotify',
      displayName: 'Spotify',
      query: spotifyPlayMatch1[1].trim(),
      actionType: 'play',
    }
  }

  const spotifyPlayMatch2 = text.match(/(?:play|stream|listen to)\s+(.+?)\s+(?:on|in)\s+spotify$/i)
  if (spotifyPlayMatch2 && spotifyPlayMatch2[1]?.trim()) {
    return {
      appId: 'spotify',
      displayName: 'Spotify',
      query: spotifyPlayMatch2[1].trim(),
      actionType: 'play',
    }
  }

  // 3. Generic "play <song/artist>" without app specified -> Defaults seamlessly to YouTube
  const genericPlayMatch = text.match(/^(?:please\s+)?(?:play|stream|listen to)\s+(.+)$/i)
  if (genericPlayMatch && genericPlayMatch[1]?.trim()) {
    return {
      appId: 'youtube',
      displayName: 'YouTube',
      query: genericPlayMatch[1].trim(),
      actionType: 'play',
    }
  }

  // 4. Targeted Search Patterns:
  // e.g. "search python tutorials on google", "search react on youtube"
  const searchMatchTargeted = text.match(/^(?:please\s+)?(?:search|find|look up)\s+(.+?)\s+(?:on|in)\s+(google|youtube|yt|github|maps)$/i)
  if (searchMatchTargeted && searchMatchTargeted[1]?.trim()) {
    const target = searchMatchTargeted[2].toLowerCase()
    const appId = target.includes('yt') || target.includes('youtube') ? 'youtube' : target === 'github' ? 'github' : target === 'maps' ? 'maps' : 'google'
    const displayName = appId === 'youtube' ? 'YouTube' : appId === 'github' ? 'GitHub' : appId === 'maps' ? 'Google Maps' : 'Google'
    return {
      appId,
      displayName,
      query: searchMatchTargeted[1].trim(),
      actionType: 'search',
    }
  }

  // 5. Generic Search Patterns:
  // e.g. "search python roadmap", "google machine learning"
  const genericSearchMatch = text.match(/^(?:please\s+)?(?:search(?:\s+for)?|google|look up|find)\s+(.+)$/i)
  if (genericSearchMatch && genericSearchMatch[1]?.trim()) {
    return {
      appId: 'google',
      displayName: 'Google',
      query: genericSearchMatch[1].trim(),
      actionType: 'search',
    }
  }

  // 6. Direct Application Launch from Allowlist
  for (const entry of PHRASE_MAP) {
    for (const pattern of entry.patterns) {
      if (pattern.test(text)) {
        return {
          appId: entry.appId,
          displayName: entry.displayName,
          actionType: 'open',
        }
      }
    }
  }

  // 7. Universal Smart Search Fallback:
  // For any command or question (e.g. "what is the weather", "who is alan turing", etc.),
  // provide a graceful, instant Google search instead of failing or throwing errors.
  return {
    appId: 'google',
    displayName: 'Google Search',
    query: text.replace(/^(?:please\s+)?(?:tell me|what is|who is|where is|how to)\s+/i, '').trim() || text,
    actionType: 'search',
  }
}

/** Check whether the text looks like a "launch / open application" intent */
export function isLaunchIntent(text: string): boolean {
  if (/\b(open|launch|start|run|show|access|play|stream|search|find|google)\b/i.test(text)) return true
  return resolveAppIntent(text) !== null
}
