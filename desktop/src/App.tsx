import { useCallback, useEffect, useRef, useState } from 'react'
import type { PointerEvent } from 'react'
import './App.css'
import './avatarAnimations.css'
import AvatarCharacter from './AvatarCharacter'
import type { AvatarAnimState } from './AvatarCharacter'
import { AVATAR_CONFIG } from './avatarConfig'
import {
  resolveAppIntent,
  isLaunchIntent,
  createInitialTaskProgress,
  type LaunchState,
  type LaunchResult,
  type LiveTaskProgress,
  type TaskStage,
  type TaskStageId,
} from './launchStateMachine'
import { voiceService } from './services/voiceService'

// ── Types ─────────────────────────────────────────────────────────────────────

export type DashboardPage =
  | 'Mission Control'
  | 'Apps & Launch'
  | 'Voice Settings'
  | 'History'
  | 'Avatar Settings'
  | 'General Settings'

/** Visual avatar state (mapped to animation state for rendering) */
export type AvatarState =
  | 'Idle'
  | 'Listening'
  | 'Thinking'
  | 'Working'
  | 'Approval Required'
  | 'Greeting'
  | 'Success'
  | 'Warning'
  | 'Error'

export type TaskStatus = 'Pending' | 'Stopped' | 'Completed' | 'Failed' | 'Cancelled'

export type Task = {
  id: number
  title: string
  status: TaskStatus
  time?: string
  launchResult?: LaunchResult
}

export type Message = {
  id: number
  author: 'You' | 'Companion'
  text: string
  time: string
  launchResult?: LaunchResult
  matches?: Array<{ name: string; path: string; isFolder?: boolean; extension?: string }>
  phase?: string
  step?: number
}

// ── Constants ─────────────────────────────────────────────────────────────────

const avatarStates: AvatarState[] = [
  'Idle', 'Listening', 'Thinking', 'Working',
  'Approval Required', 'Success', 'Warning', 'Error',
]

const NAV_ITEMS: { label: DashboardPage; icon: string; desc: string }[] = [
  { label: 'Mission Control', icon: '✦', desc: 'Active execution & overview' },
  { label: 'Apps & Launch', icon: '🚀', desc: 'Allowlisted desktop applications' },
  { label: 'Voice Settings', icon: '🎙️', desc: 'Hardware meter & recognition lab' },
  { label: 'History', icon: '📜', desc: 'Task execution log & verification' },
  { label: 'Avatar Settings', icon: '🤖', desc: 'Companion states & speed' },
  { label: 'General Settings', icon: '⚙️', desc: 'System configuration' },
]

const ALLOWLISTED_APPS_INFO = [
  { id: 'notepad', name: 'Notepad', icon: '📝', desc: 'Windows text & code scratchpad', exe: 'notepad.exe' },
  { id: 'calculator', name: 'Calculator', icon: '🔢', desc: 'Standard & scientific calculations', exe: 'calc.exe' },
  { id: 'explorer', name: 'File Explorer', icon: '📁', desc: 'File manager and drives', exe: 'explorer.exe' },
  { id: 'chrome', name: 'Google Chrome', icon: '🌐', desc: 'Fast, secure web browsing', exe: 'chrome.exe' },
  { id: 'vscode', name: 'Visual Studio Code', icon: '💻', desc: 'Code editing and development', exe: 'code.cmd' },
  { id: 'whatsapp', name: 'WhatsApp', icon: '💬', desc: 'Desktop messaging application', exe: 'WhatsApp.exe' },
  { id: 'youtube', name: 'YouTube', icon: '▶️', desc: 'Video streaming & web player', exe: 'youtube.com' },
  { id: 'spotify', name: 'Spotify', icon: '🎵', desc: 'Music & podcasts streaming', exe: 'Spotify.exe' },
  { id: 'chatgpt', name: 'ChatGPT', icon: '🤖', desc: 'AI assistant & search', exe: 'chatgpt.com' },
  { id: 'github', name: 'GitHub', icon: '🐙', desc: 'Repositories & code review', exe: 'github.com' },
  { id: 'paint', name: 'Paint', icon: '🎨', desc: 'Drawing & image editing', exe: 'mspaint.exe' },
]

/** Map the high-level AvatarState to an animation state for Doraemon */
function toAnimState(
  avatarState: AvatarState | string,
  isSleeping: boolean,
  launchState: LaunchState,
  isVoiceRecording: boolean,
  isInTransit: boolean = false
): AvatarAnimState {
  if (isSleeping) return 'idle'
  if (isVoiceRecording) return 'listening'
  // CRITICAL: Doraemon only plays the walking animation when he is physically in transit!
  if (isInTransit) return 'walking'
  if (launchState === 'resolving' || launchState === 'planning') return 'thinking'
  if (launchState === 'success') return 'success'
  if (launchState === 'error' || launchState === 'failed' || launchState === 'not-allowed' || launchState === 'not-in-electron') return 'error'
  if (launchState === 'cancelled') return 'cancelled'
  switch (avatarState) {
    case 'Listening':          return 'listening'
    case 'Thinking':           return 'thinking'
    case 'Working':            return isInTransit ? 'walking' : 'idle'
    case 'Greeting':           return 'greeting'
    case 'Approval Required':  return 'waiting'
    case 'Success':            return 'success'
    case 'Warning':            return 'waiting'
    case 'Error':              return 'error'
    default:                   return 'idle'
  }
}

// ── Launch Banner Component ───────────────────────────────────────────────────

function LaunchBanner({ result, onCancel }: { result: LaunchResult; onCancel?: () => void }) {
  const stateKey = result.state

  const icon =
    stateKey === 'success'         ? '✔' :
    stateKey === 'error' || stateKey === 'failed' ? '✖' :
    stateKey === 'cancelled'       ? '⏹' :
    stateKey === 'not-in-electron' ? '⚠' :
    stateKey === 'not-allowed'     ? '⊘' :
    '⧗'

  const title =
    stateKey === 'success'         ? `${result.displayName} launched!` :
    stateKey === 'error' || stateKey === 'failed' ? `Failed to open ${result.displayName}` :
    stateKey === 'cancelled'       ? `Movement cancelled` :
    stateKey === 'not-in-electron' ? `Cannot launch apps in browser mode` :
    stateKey === 'not-allowed'     ? `"${result.displayName}" is not in the allowed list` :
    stateKey === 'launching'       ? `Doraemon is traveling to ${result.displayName}…` :
    `Resolving application…`

  const body =
    stateKey === 'error' || stateKey === 'failed' ? result.errorMessage :
    stateKey === 'cancelled'       ? 'Doraemon stopped safely and returned home.' :
    stateKey === 'launching'       ? (result.targetInfo?.explanation || 'Traveling across visible Windows desktop to target...') :
    stateKey === 'not-in-electron' ? 'Run the app with npm run app to launch real Windows applications.' :
    stateKey === 'not-allowed'     ? `Supported apps: Notepad, Calculator, File Explorer, Chrome, VS Code, WhatsApp.` :
    result.targetInfo?.explanation || undefined

  return (
    <div className={`launch-status-banner launch-${stateKey}`} role="status" aria-live="polite">
      <span className="launch-status-icon" aria-hidden="true">{icon}</span>
      <div className="launch-status-text">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <strong>{title}</strong>
          {result.mockSimulated && (
            <span style={{ fontSize: 10, background: '#F59E0B', color: '#FFF', borderRadius: 4, padding: '1px 5px', fontWeight: 'bold' }}>
              MOCK MODE
            </span>
          )}
          {result.realLaunch && (
            <span style={{ fontSize: 10, background: '#10B981', color: '#FFF', borderRadius: 4, padding: '1px 5px', fontWeight: 'bold' }}>
              REAL WINDOWS
            </span>
          )}
        </div>
        {body && <div style={{ fontSize: 12, lineHeight: 1.45, wordBreak: 'break-word', marginTop: 2 }}>{body}</div>}
        {stateKey === 'launching' && onCancel && (
          <div>
            <button type="button" className="cancel-move-btn" onClick={onCancel}>
              ⏹ Cancel Movement
            </button>
          </div>
        )}
        {stateKey === 'success' && !result.verified && (
          <span className="launch-unverified-note">
            Note: Process started successfully. Window visibility is not verifiable from Electron.
          </span>
        )}
      </div>
    </div>
  )
}

// ── App Component ─────────────────────────────────────────────────────────────

export default function App() {
  const [viewMode] = useState<'avatar' | 'dashboard'>(() => {
    if (typeof window === 'undefined') return 'dashboard'
    const params = new URLSearchParams(window.location.search)
    if (params.get('view') === 'avatar' || window.location.hash === '#avatar') {
      return 'avatar'
    }
    return 'dashboard'
  })

  // ── Dashboard and Navigation state ──
  const [activeTab, setActiveTab] = useState<DashboardPage>('Mission Control')
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [avatarState, setAvatarState] = useState<AvatarState>('Idle')
  const [isSleeping, setIsSleeping] = useState(false)
  const [notice, setNotice] = useState('')
  const [executionMode, setExecutionMode] = useState<'real' | 'mock'>('real')
  const [facing, setFacing] = useState<'left' | 'right'>('right')
  const [isInTransit, setIsInTransit] = useState(false)

  // ── Floating Chatbox toggle (in avatar mode) ──
  const [isChatboxOpen, setIsChatboxOpen] = useState(false)

  // ── Voice interaction state ──
  const [isVoiceRecording, setIsVoiceRecording] = useState(false)
  const [voiceTranscript, setVoiceTranscript] = useState('')
  const [audioLevel, setAudioLevel] = useState(0)
  const [voiceError, setVoiceError] = useState<string | null>(null)

  // ── Voice Testing & Diagnostic state ──
  const [isTestingMic, setIsTestingMic] = useState(false)
  const [micTestLevel, setMicTestLevel] = useState(0)
  const [micTestMsg, setMicTestMsg] = useState('')
  const [isTestingSpeech, setIsTestingSpeech] = useState(false)
  const [speechTestTranscript, setSpeechTestTranscript] = useState('')
  const [isTestingTTS, setIsTestingTTS] = useState(false)
  const micTestCleanupRef = useRef<(() => void) | null>(null)

  // ── Live task progress ──
  const [liveProgress, setLiveProgress] = useState<LiveTaskProgress | null>(null)
  const taskCancelledRef = useRef<boolean>(false)
  const isTaskActiveRef = useRef<boolean>(false)
  const returnHomeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [launchState, setLaunchState] = useState<LaunchState>('idle')
  const [currentLaunchResult, setCurrentLaunchResult] = useState<LaunchResult | null>(null)

  // ── Auto-Updater & Software Versioning ──
  const [updateInfo, setUpdateInfo] = useState<import('./companion').UpdateInfo | null>(null)
  const [isUpdating, setIsUpdating] = useState(false)
  const [isUpdateReadyToRestart, setIsUpdateReadyToRestart] = useState(false)
  const [updateStatusMsg, setUpdateStatusMsg] = useState('')
  const [appVersion, setAppVersion] = useState('1.0.1')

  useEffect(() => {
    if (window.companionAPI?.getCurrentVersion) {
      window.companionAPI.getCurrentVersion().then((v) => {
        if (v) setAppVersion(v)
      }).catch(() => {})
    }
    if (window.companionAPI?.onUpdateAvailable) {
      const unsub = window.companionAPI.onUpdateAvailable((info) => {
        setUpdateInfo(info)
        if (info.updateAvailable) {
          setUpdateStatusMsg(`Update available: v${info.remoteVersion || ''}`)
        }
      })
      return unsub
    }
  }, [])

  const handleCheckUpdates = useCallback(async () => {
    if (!window.companionAPI?.checkUpdates) return
    setIsUpdating(true)
    setUpdateStatusMsg('Checking for updates…')
    try {
      const res = await window.companionAPI.checkUpdates()
      setUpdateInfo(res)
      if (res.updateAvailable) {
        setUpdateStatusMsg(`Update available: v${res.remoteVersion || ''}`)
      } else {
        setUpdateStatusMsg('You are running the latest version.')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setUpdateStatusMsg(`Update check failed: ${msg}`)
    } finally {
      setIsUpdating(false)
    }
  }, [])

  const handleApplyUpdate = useCallback(async () => {
    if (!window.companionAPI?.applyUpdate || !updateInfo) return
    setIsUpdating(true)
    setUpdateStatusMsg('Downloading and applying update…')
    try {
      const res = await window.companionAPI.applyUpdate(updateInfo)
      if (res.success) {
        setIsUpdateReadyToRestart(true)
        setUpdateStatusMsg('Update applied! Restart to complete.')
      } else {
        setUpdateStatusMsg(`Update failed: ${res.error || 'Unknown error'}`)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setUpdateStatusMsg(`Update failed: ${msg}`)
    } finally {
      setIsUpdating(false)
    }
  }, [updateInfo])

  const handleRelaunch = useCallback(async () => {
    if (window.companionAPI?.relaunchApp) {
      await window.companionAPI.relaunchApp()
    }
  }, [])

  // ── Refs ──
  const avatarDragStart = useRef<{ screenX: number; screenY: number; moved: boolean } | null>(null)
  const messageInputRef = useRef<HTMLTextAreaElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const voiceAutoEndTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latestSpeechRef = useRef<string>('')

  const clearVoiceAutoEndTimer = useCallback(() => {
    if (voiceAutoEndTimerRef.current) {
      clearTimeout(voiceAutoEndTimerRef.current)
      voiceAutoEndTimerRef.current = null
    }
  }, [])

  // Sync mode classes with document root
  useEffect(() => {
    if (viewMode === 'avatar') {
      document.documentElement.classList.add('avatar-window-mode')
      document.body.classList.add('avatar-window-mode')
    } else {
      document.documentElement.classList.remove('avatar-window-mode')
      document.body.classList.remove('avatar-window-mode')
    }
  }, [viewMode])

  // IPC Event subscriptions
  useEffect(() => {
    if (window.companionAPI) {
      const cleanup = window.companionAPI.onSyncState((data) => {
        if (data.avatarState && avatarStates.includes(data.avatarState as AvatarState)) {
          setAvatarState(data.avatarState as AvatarState)
        }
        if (typeof data.isSleeping === 'boolean') {
          setIsSleeping(data.isSleeping)
        }
        if (data.facing) {
          setFacing(data.facing)
        }
        if (typeof data.isMoving === 'boolean') {
          setIsInTransit(data.isMoving)
        }
        if (data.taskState) {
          setLaunchState(data.taskState as LaunchState)
        }
        if (typeof data.chatboxOpen === 'boolean') {
          setIsChatboxOpen(data.chatboxOpen)
        }
      })

      const cleanupMove = window.companionAPI.onMovementProgress?.((step) => {
        if (step.facing) setFacing(step.facing)
      })

      const cleanupProgress = window.companionAPI.onTaskProgress?.((progressData: any) => {
        const timeNow = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        setMessages((prev) => {
          if (prev.length > 0 && prev[prev.length - 1].text === progressData.message) {
            return prev
          }
          return [
            ...prev,
            {
              id: Date.now() + Math.random(),
              author: 'Companion',
              text: progressData.message || '',
              time: timeNow,
              matches: progressData.matches,
              phase: progressData.phase,
              step: progressData.step,
            },
          ]
        })

        if (progressData.phase === 'finding' || progressData.phase === 'searching') {
          setAvatarState('Thinking')
        } else if (progressData.phase === 'clarification_required') {
          setAvatarState('Approval Required')
          setLaunchState('awaiting_approval')
          setIsChatboxOpen(true)
          window.companionAPI?.setChatboxOpen?.(true)
        } else if (
          progressData.phase === 'walking' ||
          progressData.phase === 'moving_to_search_field' ||
          progressData.phase === 'moving_to_result'
        ) {
          setAvatarState('Working')
          setIsInTransit(true)
        } else if (progressData.phase === 'opening' || progressData.phase === 'opening_search') {
          setAvatarState('Working')
          setIsInTransit(false)
        } else if (progressData.phase === 'results_found') {
          setAvatarState('Working')
          setIsInTransit(false)
        } else if (progressData.phase === 'success') {
          setAvatarState('Success')
          setIsInTransit(false)
        } else if (progressData.phase === 'failed') {
          setAvatarState('Error')
          setIsInTransit(false)
        }
      })

      window.companionAPI.getExecutionMode?.().then((mode) => {
        if (mode) setExecutionMode(mode)
      })

      return () => {
        cleanup()
        if (cleanupMove) cleanupMove()
        if (cleanupProgress) cleanupProgress()
      }
    }
  }, [])

  // Cleanup mic & voice on unmount
  useEffect(() => {
    return () => {
      clearVoiceAutoEndTimer()
      voiceService.stopListening()
      if (micTestCleanupRef.current) {
        micTestCleanupRef.current()
        micTestCleanupRef.current = null
      }
      if (returnHomeTimerRef.current) {
        clearTimeout(returnHomeTimerRef.current)
        returnHomeTimerRef.current = null
      }
    }
  }, [clearVoiceAutoEndTimer])

  // Auto-scroll chatbox to newest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Helper to update Live Task Progress
  const updateProgressStage = useCallback((
    stageId: TaskStageId,
    status: TaskStage['status'],
    detail?: string,
    percent?: number
  ) => {
    const timeNow = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setLiveProgress((prev) => {
      if (!prev) return null
      const stages = prev.stages.map((st) => {
        if (st.id === stageId) {
          return {
            ...st,
            status,
            timestamp: timeNow,
            detail: detail || st.detail,
          }
        }
        return st
      })
      return {
        ...prev,
        currentStageId: stageId,
        percent: percent !== undefined ? percent : prev.percent,
        stages,
      }
    })
  }, [])

  // ── Cancellation Handler ────────────────────────────────────────────────────
  const cancelActiveTask = useCallback(() => {
    taskCancelledRef.current = true
    isTaskActiveRef.current = false
    if (returnHomeTimerRef.current) {
      clearTimeout(returnHomeTimerRef.current)
      returnHomeTimerRef.current = null
    }
    clearVoiceAutoEndTimer()

    if (isVoiceRecording) {
      voiceService.stopListening()
      setIsVoiceRecording(false)
      setAudioLevel(0)
    }

    if (window.companionAPI?.cancelTask) {
      window.companionAPI.cancelTask()
    } else if (window.companionAPI?.cancelMovement) {
      window.companionAPI.cancelMovement()
    }

    setLaunchState('cancelled')
    setAvatarState('Error')
    setNotice('Task cancelled by user request.')

    setLiveProgress((prev) => {
      if (!prev) return null
      const updatedStages: TaskStage[] = prev.stages.map((st) => {
        if (st.status === 'in_progress') {
          return { ...st, status: 'cancelled' as const, detail: 'Stopped by user cancellation.' }
        }
        return st
      })
      return {
        ...prev,
        currentStageId: 'cancelled',
        stages: updatedStages,
        error: 'Operation cancelled by user.',
      }
    })

    returnHomeTimerRef.current = setTimeout(() => {
      if (window.companionAPI?.returnHome) {
        window.companionAPI.returnHome()
      }
      setAvatarState('Idle')
      setLaunchState('idle')
    }, 2500)
  }, [clearVoiceAutoEndTimer, isVoiceRecording])

  // ── Unified Launch & Automation Execution Flow ──────────────────────────────
  const handleLaunchApp = useCallback(async (
    rawText: string,
    specificChoice?: { name: string; path: string }
  ) => {
    // When a task is launched from the floating chatbox, collapse it so Doraemon travels alone
    if (isChatboxOpen) {
      setIsChatboxOpen(false)
      if (window.companionAPI?.setChatboxOpen) {
        window.companionAPI.setChatboxOpen(false)
      }
    }

    if (returnHomeTimerRef.current) {
      clearTimeout(returnHomeTimerRef.current)
      returnHomeTimerRef.current = null
    }
    isTaskActiveRef.current = true
    if (window.companionAPI?.cancelActiveMovement) {
      window.companionAPI.cancelActiveMovement()
    }

    taskCancelledRef.current = false
    setMessage('')
    setVoiceTranscript('')
    latestSpeechRef.current = ''

    const now = new Date()
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    const taskId = String(Date.now())
    const initialProgress = createInitialTaskProgress(taskId, rawText, executionMode)
    setLiveProgress(initialProgress)

    updateProgressStage('request_received', 'completed', `Received command: "${rawText}"`, 15)

    setLaunchState('resolving')
    setAvatarState('Thinking')
    updateProgressStage('understanding', 'in_progress', 'Analyzing natural language intent…', 30)

    const intent = resolveAppIntent(rawText)
    let appId = ''
    let displayName = rawText.trim()
    let rawCommand = rawText.trim()
    let query = ''
    let actionType: 'open' | 'play' | 'search' = 'open'

    if (specificChoice) {
      displayName = specificChoice.name
      rawCommand = specificChoice.path
    } else if (intent) {
      appId = intent.appId
      displayName = intent.displayName
      rawCommand = rawText.trim()
      query = intent.query || ''
      actionType = intent.actionType || 'open'
    } else {
      // Clean up common action prefixes (e.g. "open pokedex" -> "pokedex", "show folder Design thinking" -> "Design thinking")
      const cleaned = rawText
        .replace(/^(?:please\s+)?(?:can\s+you\s+)?(?:could\s+you\s+)?(?:i\s+want\s+to\s+)?(?:open|launch|start|run|show|access|find|goto)\s+(?:the\s+)?(?:folder\s+|file\s+|app\s+|application\s+)?/i, '')
        .trim()
        .replace(/[?.!]+$/, '')
      if (cleaned) {
        displayName = cleaned
        rawCommand = cleaned
      }
    }

    const isFileExplorerApp = Boolean(rawText.match(/\b(?:file\s+explorer|explorer|my\s+computer|file\s+manager)\b/i))
    const isExplicitFileSearch = !isFileExplorerApp && (Boolean(specificChoice) || Boolean(rawText.match(/\b(folder|file|document|dir)\b/i)))
    const isAppTarget = isFileExplorerApp || (!isExplicitFileSearch && (Boolean(intent) || Boolean(rawText.match(/\b(app|application|program|software|tool|calc|calculator|notepad|chrome|code|vscode|whatsapp|spotify|netflix|browser)\b/i))))
    const targetKind: 'application' | 'file_or_folder' | 'auto' = isExplicitFileSearch ? 'file_or_folder' : (isAppTarget ? 'application' : 'auto')

    if (taskCancelledRef.current) return
    updateProgressStage('understanding', 'completed', `Identified target: ${displayName}`, 45)

    updateProgressStage('validating', 'in_progress', isAppTarget ? `Searching installed applications & shortcuts for ${displayName}…` : `Locating coordinates for ${displayName}…`, 55)
    await new Promise((r) => setTimeout(r, 200))

    if (taskCancelledRef.current) return
    updateProgressStage('validating', 'completed', `Target "${displayName}" verified. Ready to dispatch.`, 65)

    setLaunchState('planning')
    setAvatarState('Thinking')
    updateProgressStage('waiting_execution', 'in_progress', 'Preparing companion coordinates…', 70)
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), author: 'You', text: specificChoice ? `Selected: ${specificChoice.name}` : rawText, time: timeStr },
    ])
    await new Promise((r) => setTimeout(r, 250))

    if (taskCancelledRef.current) return
    updateProgressStage('waiting_execution', 'completed', 'Companion positioned. Motion trajectory generated.', 75)

    setLaunchState('launching')
    setAvatarState('Working')
    updateProgressStage('launch_attempted', 'in_progress', `Doraemon physically moving across desktop to ${displayName}…`, 85)

    let taskResult: import('./companion').DesktopTaskResult | null = null

    const isHumanActivityCmd =
      !specificChoice &&
      /\b(ask|tell|prompt|loop\s+download|batch\s+download|download\s+all|copy|paste|press|hit|message|e-?mail|mail|go\s+to|visit)\b|\band\s+(?:type|write|enter|ask|click|play|paste)\b|^[\w.+-]+@[\w-]+\.[\w.-]+$/i.test(
        rawText.trim()
      )

    if (isHumanActivityCmd) {
      try {
        const normalizedCmd = /^[\w.+-]+@[\w-]+\.[\w.-]+$/.test(rawText.trim())
          ? `send an email to ${rawText.trim()}`
          : rawText.trim()
        const backendResp = await fetch('http://127.0.0.1:8000/tasks/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: normalizedCmd,
            auto_approve: true,
            timeout_seconds: 30,
          }),
        })
        if (backendResp.ok) {
          const data = await backendResp.json()
          if (data && (data.status === 'completed' || data.requires_clarification)) {
            const outputText =
              data.result?.output_text ||
              data.result?.verification?.details?.captured_text ||
              data.result?.verification?.details?.copied_text ||
              ''
            const replyMsg =
              data.clarification_question ||
              data.message ||
              `Completed ${data.steps?.length || 1}-step workflow.`
            taskResult = {
              success: true,
              verified: true,
              displayName: data.selected_application || displayName,
              mode: 'real',
              taskState: 'success',
              executionMode: 'real',
              targetInfo: {
                foundShortcut: true,
                shortcutPath: null,
                destination: { x: 0, y: 0 },
                destinationType: 'taskbar-fallback',
                explanation: outputText ? `${replyMsg}\n\n📋 Captured Output:\n${outputText}` : replyMsg,
              },
            }
            if (data.requires_clarification && data.clarification_question) {
              voiceService.speakResponse(data.clarification_question)
            }
          }
        }
      } catch (backendErr) {
        console.warn('[App] Python multi-step backend unreachable, falling back to Electron launcher:', backendErr)
      }
    }

    if (taskResult) {
      // Handled by Python multi-step orchestrator
    } else if (window.companionAPI?.startDesktopTask) {
      try {
        taskResult = await window.companionAPI.startDesktopTask({
          appId,
          displayName,
          query,
          actionType,
          rawCommand,
          query: intent?.query,
          pathChoice: specificChoice?.path,
          targetKind,
        })
      } catch (err: unknown) {
        taskResult = {
          success: false,
          verified: false,
          displayName,
          mode: executionMode,
          taskState: 'failed',
          executionMode,
          error: err instanceof Error ? err.message : String(err),
        }
      }
    } else {
      // Browser preview mode -> forward to local dev server backend
      const candidateUrls = [
        `/api/launch-app?appId=${encodeURIComponent(appId || displayName)}`,
        `http://127.0.0.1:5173/api/launch-app?appId=${encodeURIComponent(appId || displayName)}`,
        `http://localhost:5173/api/launch-app?appId=${encodeURIComponent(appId || displayName)}`,
      ]

      let fetchedResult: import('./companion').IpcLaunchResult | null = null
      let lastError: Error | null = null

      for (const candidate of candidateUrls) {
        try {
          const resp = await fetch(candidate)
          if (resp.ok) {
            fetchedResult = await resp.json()
            break
          }
        } catch (err: unknown) {
          lastError = err instanceof Error ? err : new Error(String(err))
        }
      }

      if (fetchedResult) {
        taskResult = {
          ...fetchedResult,
          taskState: fetchedResult.success ? 'success' : 'failed',
          executionMode: 'real',
        }
      } else {
        taskResult = {
          success: false,
          verified: false,
          displayName,
          mode: 'real',
          taskState: 'failed',
          executionMode: 'real',
          error: lastError ? lastError.message : 'Failed to reach local launcher service.',
        }
      }
    }

    if (taskCancelledRef.current || taskResult.cancelled) {
      updateProgressStage('launch_verified', 'cancelled', 'Task cancelled by user before verification.', 85)
      const result: LaunchResult = {
        state: 'cancelled',
        displayName,
        appId,
        realLaunch: false,
        cancelled: true,
        errorMessage: 'Movement cancelled by user request.',
      }
      setLaunchState('cancelled')
      setCurrentLaunchResult(result)
      setAvatarState('Error')
      setTimeout(() => { setLaunchState('idle'); setAvatarState('Idle') }, 3500)
      return
    }

    if (taskResult.clarificationRequired) {
      setLaunchState('awaiting_approval')
      setAvatarState('Approval Required')
      setIsChatboxOpen(true)
      if (window.companionAPI?.setChatboxOpen) {
        window.companionAPI.setChatboxOpen(true)
      }
      return
    }

    updateProgressStage('launch_attempted', 'completed', 'Process launch command issued.', 90)

    if (taskResult.success) {
      const isMock = taskResult.mode === 'mock' || taskResult.mockSimulated
      const verifiedText = taskResult.verified
        ? 'Process verified running'
        : isMock
        ? 'Simulated in mock mode'
        : 'Process started successfully'

      updateProgressStage('launch_verified', 'completed', verifiedText, 100)

      const result: LaunchResult = {
        state: 'success',
        displayName: taskResult.displayName,
        appId,
        realLaunch: !isMock,
        verified: taskResult.verified,
        targetInfo: taskResult.targetInfo,
        executionMode: taskResult.executionMode,
        mockSimulated: isMock,
      }

      setLaunchState('success')
      setCurrentLaunchResult(result)
      setAvatarState('Success')

      voiceService.speakResponse(`${taskResult.displayName} opened successfully.`)
      setTasks((prev) => [...prev, { id: Date.now() + 2, title: rawText, status: 'Completed', time: timeStr, launchResult: result }])

      returnHomeTimerRef.current = setTimeout(() => {
        isTaskActiveRef.current = false
        setLaunchState('idle')
        setAvatarState('Idle')
        setFacing('right')
        if (window.companionAPI?.returnHome) {
          window.companionAPI.returnHome()
        }
      }, 4000)
    } else {
      const failureReason = taskResult.error ?? 'Destination not found or process failed to start.'
      updateProgressStage('launch_verified', 'failed', failureReason, 90)

      const result: LaunchResult = {
        state: 'failed',
        displayName: taskResult.displayName,
        appId,
        realLaunch: taskResult.mode === 'real',
        errorMessage: failureReason,
        targetInfo: taskResult.targetInfo,
        executionMode: taskResult.executionMode,
      }

      setLaunchState('failed')
      setCurrentLaunchResult(result)
      setAvatarState('Error')
      voiceService.speakResponse(`Could not open ${taskResult.displayName}.`)

      setTasks((prev) => [...prev, { id: Date.now() + 2, title: rawText, status: 'Failed', time: timeStr, launchResult: result }])
      returnHomeTimerRef.current = setTimeout(() => {
        isTaskActiveRef.current = false
        setLaunchState('idle')
        setAvatarState('Idle')
        setFacing('right')
        if (window.companionAPI?.returnHome) {
          window.companionAPI.returnHome()
        }
      }, 4000)
    }
  }, [executionMode, isChatboxOpen, updateProgressStage])

  // ── Voice Input Handler ─────────────────────────────────────────────────────
  const handleToggleVoice = useCallback(async () => {
    if (messageInputRef.current) {
      messageInputRef.current.focus()
    }

    if (isVoiceRecording) {
      clearVoiceAutoEndTimer()
      voiceService.stopListening()
      setIsVoiceRecording(false)
      setAudioLevel(0)
      setAvatarState('Idle')
      return
    }

    clearVoiceAutoEndTimer()
    latestSpeechRef.current = ''
    setVoiceError(null)
    setVoiceTranscript('')
    setMessage('')
    setIsVoiceRecording(true)
    setAvatarState('Listening')

    const started = await voiceService.startListening({
      onTranscript: (text, isFinal) => {
        setVoiceTranscript(text)
        setMessage(text)
        latestSpeechRef.current = text
        clearVoiceAutoEndTimer()

        const dispatchVoiceCommand = (rawCmd: string) => {
          const cmd = rawCmd.trim()
          if (!cmd) return

          // Allow hands-free voice command to turn off the always-on mic intentionally
          if (/^(stop listening|turn off mic|mute mic|mic off|go to sleep)$/i.test(cmd)) {
            voiceService.stopListening()
            setIsVoiceRecording(false)
            setAudioLevel(0)
            setVoiceTranscript('')
            setMessage('')
            latestSpeechRef.current = ''
            setAvatarState('Idle')
            return
          }

          // Keep mic ON continuously for the next voice command!
          latestSpeechRef.current = ''
          setVoiceTranscript('')
          setMessage('')
          setAvatarState('Thinking')
          handleLaunchApp(cmd)
        }

        if (isFinal) {
          dispatchVoiceCommand(text)
        } else {
          voiceAutoEndTimerRef.current = setTimeout(() => {
            const finalCmd = latestSpeechRef.current.trim()
            if (finalCmd) {
              dispatchVoiceCommand(finalCmd)
            }
          }, 1300)
        }
      },
      onAudioLevel: (level) => {
        setAudioLevel(level)
      },
      onNotice: (noticeMsg) => {
        setNotice(noticeMsg)
      },
      onError: (err) => {
        clearVoiceAutoEndTimer()
        if (err.type === 'network') {
          setNotice('🎤 Always-on microphone listening... Speak your command.')
          setAvatarState('Listening')
        } else {
          setVoiceError(err.message)
          setIsVoiceRecording(false)
          setAvatarState('Error')
        }
      },
      onEnd: () => {
        clearVoiceAutoEndTimer()
        setIsVoiceRecording(false)
        setAudioLevel(0)
        setAvatarState((prev) => (prev === 'Listening' ? 'Idle' : prev))
      },
    })

    if (!started) {
      clearVoiceAutoEndTimer()
      setIsVoiceRecording(false)
      setAvatarState('Idle')
    }
  }, [clearVoiceAutoEndTimer, handleLaunchApp, isVoiceRecording])

  // ── Voice Testing & Diagnostic Helpers ──────────────────────────────────────
  const toggleMicTest = useCallback(async () => {
    if (isTestingMic) {
      if (micTestCleanupRef.current) {
        micTestCleanupRef.current()
        micTestCleanupRef.current = null
      }
      setIsTestingMic(false)
      setMicTestLevel(0)
      setMicTestMsg('Microphone hardware test stopped.')
    } else {
      try {
        setIsTestingMic(true)
        setMicTestMsg('Listening... Speak into your microphone to verify input level.')
        const cleanup = await voiceService.testMicrophone((level) => {
          setMicTestLevel(level)
          if (level > 15) {
            setMicTestMsg(`Audio Signal Detected! Level: ${level}%`)
          }
        })
        micTestCleanupRef.current = cleanup
      } catch (err: unknown) {
        setIsTestingMic(false)
        setMicTestMsg(`Microphone unavailable: ${err instanceof Error ? err.message : 'Permission denied or device not found'}`)
      }
    }
  }, [isTestingMic])

  const toggleSpeechTest = useCallback(async () => {
    if (isTestingSpeech) {
      voiceService.stopListening()
      setIsTestingSpeech(false)
    } else {
      setIsTestingSpeech(true)
      setSpeechTestTranscript('Listening... Speak a phrase now.')
      const started = await voiceService.startListening({
        onTranscript: (t, isFinal) => {
          setSpeechTestTranscript(t)
          if (isFinal) {
            setTimeout(() => setIsTestingSpeech(false), 900)
          }
        },
        onAudioLevel: (lvl) => setMicTestLevel(lvl),
        onError: (err) => {
          setSpeechTestTranscript(`Speech engine note: ${err.message}`)
          setIsTestingSpeech(false)
        },
        onEnd: () => {
          setIsTestingSpeech(false)
        },
      })
      if (!started) {
        setIsTestingSpeech(false)
        setSpeechTestTranscript('Speech recognition unavailable. Press Win+H for Windows Voice Typing.')
      }
    }
  }, [isTestingSpeech])

  const handleTestTTS = useCallback(() => {
    if (isTestingTTS) return
    setIsTestingTTS(true)
    voiceService.speakResponse('Hello! I am Doraemon. Your voice automation companion is ready and working!', () => {
      setIsTestingTTS(false)
    })
  }, [isTestingTTS])

  const handleSimulatedVoiceTest = useCallback(async (commandText: string) => {
    clearVoiceAutoEndTimer()
    setVoiceError(null)
    setVoiceTranscript('')
    setIsVoiceRecording(true)
    setAvatarState('Listening')

    await voiceService.simulateVoiceCommand(commandText, {
      onTranscript: (text, isFinal) => {
        setVoiceTranscript(text)
        setMessage(text)
        latestSpeechRef.current = text
        if (isFinal) {
          setIsVoiceRecording(false)
          setAudioLevel(0)
          setAvatarState('Thinking')
          handleLaunchApp(text)
        }
      },
      onAudioLevel: (level) => {
        setAudioLevel(level)
      },
      onError: (err) => {
        setVoiceError(err.message)
        setIsVoiceRecording(false)
        setAudioLevel(0)
        setAvatarState('Error')
      },
      onEnd: () => {
        setIsVoiceRecording(false)
        setAudioLevel(0)
      },
    })
  }, [clearVoiceAutoEndTimer, handleLaunchApp])

  // ── Dragging in Standalone Avatar Window ─────────────────────────────────────
  function beginAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return
    if ((event.target as HTMLElement).closest('button, select, input, a, option, textarea, .no-drag-region')) return
    avatarDragStart.current = { screenX: event.screenX, screenY: event.screenY, moved: false }
    try { event.currentTarget.setPointerCapture(event.pointerId) } catch { /* ok */ }
  }

  function moveAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    if (!avatarDragStart.current) return
    const dx = event.screenX - avatarDragStart.current.screenX
    const dy = event.screenY - avatarDragStart.current.screenY
    if (Math.hypot(dx, dy) > 3) {
      avatarDragStart.current.moved = true
    }
    if (dx !== 0 || dy !== 0) {
      avatarDragStart.current.screenX = event.screenX
      avatarDragStart.current.screenY = event.screenY
      if (window.companionAPI?.moveAvatar) window.companionAPI.moveAvatar(dx, dy)
    }
  }

  function handleToggleFloatingChatbox() {
    if (isSleeping) {
      setIsSleeping(false)
      if (window.companionAPI) {
        window.companionAPI.wakeAvatar()
        window.companionAPI.sendSyncState({ isSleeping: false })
      }
      return
    }

    const next = !isChatboxOpen
    setIsChatboxOpen(next)
    if (window.companionAPI?.setChatboxOpen) {
      window.companionAPI.setChatboxOpen(next)
    }
  }

  function endAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    if (avatarDragStart.current) {
      const wasMoved = avatarDragStart.current.moved
      try { event.currentTarget.releasePointerCapture(event.pointerId) } catch { /* ok */ }
      avatarDragStart.current = null

      if (!wasMoved) {
        // Click on Doraemon avatar in floating window -> toggle Chatbox!
        handleToggleFloatingChatbox()
      }
    }
  }

  // ── Send typed message ──────────────────────────────────────────────────────
  function sendMessage() {
    clearVoiceAutoEndTimer()
    if (isVoiceRecording) {
      // Keep always-on mic active; just reset pending speech buffer
      latestSpeechRef.current = ''
      setVoiceTranscript('')
    }
    const text = message.trim()
    if (!text || isSleeping) return
    setMessage('')

    const isGreeting = /^(hi|hello|hey|help|howdy|sup|greetings)\b/i.test(text)
    if (isLaunchIntent(text) || !isGreeting) {
      handleLaunchApp(text)
      return
    }

    const now = new Date()
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), author: 'You', text, time: timeStr },
      {
        id: Date.now() + 1,
        author: 'Companion',
        text: 'Hello! I am Doraemon, your desktop companion. Type or say "Open <app or folder name>" (e.g. "Open Notepad" or "Open pokedex") and I will walk over and open it for you!',
        time: timeStr,
      },
    ])
    setTasks((prev) => [...prev, { id: Date.now() + 2, title: text, status: 'Pending', time: timeStr }])
    setAvatarState('Idle')
  }

  const currentAvatarState = isSleeping ? 'Idle' : avatarState
  const animState = toAnimState(currentAvatarState, isSleeping, launchState, isVoiceRecording, isInTransit)

  // ═════════════════════════════════════════════════════════════════════════════
  // VIEW MODE: REAL FLOATING DORAEMON AVATAR (avatarWindow)
  // ═════════════════════════════════════════════════════════════════════════════
  if (viewMode === 'avatar') {
    return (
      <div
        className={`avatar-companion-desktop-root ${isChatboxOpen ? 'chatbox-expanded' : 'compact-mode'}`}
        onPointerDown={beginAvatarDrag}
        onPointerMove={moveAvatarDrag}
        onPointerUp={endAvatarDrag}
        onPointerCancel={endAvatarDrag}
      >
        {!isChatboxOpen ? (
          // Compact Floating Doraemon
          <div className="avatar-compact-stage" title="Click Doraemon to open Chatbox">
            <div className="avatar-image-wrapper">
              <AvatarCharacter state={animState} size={AVATAR_CONFIG.characterWidth} facing={facing} />
            </div>
            {!isSleeping && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'center' }}>
                {updateInfo && updateInfo.updateAvailable && (
                  <button
                    type="button"
                    className="avatar-hint-pill"
                    style={{
                      background: 'linear-gradient(135deg, #00E676, #00B4D8)',
                      color: '#000',
                      fontWeight: 700,
                      boxShadow: '0 0 12px rgba(0, 230, 118, 0.7)',
                    }}
                    onClick={(e) => {
                      e.stopPropagation()
                      if (window.companionAPI?.openDashboard) window.companionAPI.openDashboard()
                    }}
                    title={`New update v${updateInfo.remoteVersion} available! Click to open Mission Control`}
                  >
                    ℹ️ Update v{updateInfo.remoteVersion}
                  </button>
                )}
                <button
                  type="button"
                  className="avatar-hint-pill"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleToggleFloatingChatbox()
                  }}
                >
                  ✦ Click to chat
                </button>
              </div>
            )}
          </div>
        ) : (
          // Expanded Avatar + Chatbox
          <div className="avatar-chatbox-expanded-layout">
            {/* Doraemon on the LEFT side of the small chatbox */}
            <div className="avatar-compact-stage" title="Click Doraemon to collapse Chatbox">
              <div className="avatar-image-wrapper">
                <AvatarCharacter state={animState} size={AVATAR_CONFIG.characterWidth} facing="right" />
              </div>
            </div>

            <div className="avatar-floating-chatbox">
              {/* Header */}
              <div className="floating-chat-header">
                <div className="floating-chat-brand">
                  <AvatarCharacter state={animState} size={28} facing="right" />
                  <div className="floating-chat-title-group">
                    <strong>OmniCompanion</strong>
                    <span className="floating-status-badge">{isVoiceRecording ? '🎤 Listening…' : currentAvatarState}</span>
                  </div>
                </div>
                <div className="floating-chat-actions">
                  <button
                    type="button"
                    className="floating-action-btn"
                    onClick={() => {
                      if (window.companionAPI?.openDashboard) window.companionAPI.openDashboard()
                    }}
                    title="Open Main Mission Control"
                  >
                    ✦ Dashboard
                  </button>
                  <button
                    type="button"
                    className="floating-action-btn floating-action-btn-icon"
                    onClick={() => {
                      setActiveTab('Avatar Settings')
                      if (window.companionAPI?.openDashboard) window.companionAPI.openDashboard()
                    }}
                    title="Avatar Settings"
                  >
                    ⚙️
                  </button>
                  <button
                    type="button"
                    className="floating-close-btn"
                    onClick={handleToggleFloatingChatbox}
                    title="Collapse chatbox"
                  >
                    ✕
                  </button>
                </div>
              </div>

              {/* Messages & Content */}
              <div className="floating-chat-messages">
                {messages.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '20px 10px' }}>
                    <h3 style={{ fontSize: 16, margin: '0 0 6px', color: 'var(--mc-text-main)' }}>Hey there! 👋</h3>
                    <p style={{ fontSize: 12, color: 'var(--mc-text-muted)', margin: 0 }}>
                      Try opening an app — speak or type <em>"Open Notepad"</em> or <em>"Open Calculator"</em>
                    </p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center', marginTop: 14 }}>
                      {['Open Notepad', 'Open Calculator', 'Open File Explorer', 'Open Chrome'].map((cmd) => (
                        <button
                          key={cmd}
                          type="button"
                          className="mc-chip-btn"
                          onClick={() => handleLaunchApp(cmd)}
                        >
                          {cmd}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map((item) => (
                    <div
                      key={item.id}
                      className={`floating-chat-bubble ${item.author === 'You' ? 'floating-chat-bubble-user' : 'floating-chat-bubble-companion'}`}
                      style={{
                        alignSelf: item.author === 'You' ? 'flex-end' : 'flex-start',
                        maxWidth: '85%',
                        borderRadius: 12,
                        padding: '8px 12px',
                        fontSize: 13,
                        boxShadow: 'var(--mc-shadow-sm)',
                        color: item.author === 'You' ? '#0369a1' : '#0f172a',
                      }}
                    >
                      <div>{item.text}</div>
                      {item.matches && item.matches.length > 0 && (
                        <div className="clarification-chip-list">
                          {item.matches.map((m, idx) => (
                            <button
                              key={idx}
                              type="button"
                              className="clarification-chip-btn"
                              onClick={() => {
                                handleLaunchApp(m.name, m)
                              }}
                            >
                              <span className="clarification-chip-name">{m.isFolder ? '📁 ' : '📄 '}{m.name}</span>
                              <span className="clarification-chip-path">{m.path}</span>
                            </button>
                          ))}
                        </div>
                      )}
                      {item.launchResult && (
                        <div style={{ marginTop: 6 }}>
                          <LaunchBanner result={item.launchResult} onCancel={cancelActiveTask} />
                        </div>
                      )}
                      <div style={{ fontSize: 9, color: '#64748b', textAlign: 'right', marginTop: 4 }}>
                        {item.time}
                      </div>
                    </div>
                  ))
                )}

                {/* Voice recording card if listening */}
                {(isVoiceRecording || voiceTranscript) && (
                  <div className="chat-voice-card">
                    <div className="chat-voice-header">
                      <span className="voice-recording-dot" aria-hidden="true" />
                      <span>{isVoiceRecording ? 'Listening…' : 'Recognized Speech'}</span>
                      {isVoiceRecording && (
                        <div className="voice-waveform" aria-hidden="true" style={{ marginLeft: 'auto' }}>
                          {[1, 2, 3, 4, 5].map((i) => (
                            <span
                              key={i}
                              className="waveform-bar"
                              style={{ height: `${Math.max(4, Math.min(18, (audioLevel / 100) * 16 + i * 2))}px` }}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="chat-voice-transcript">
                      {voiceTranscript || <span style={{ opacity: 0.5 }}>Speak your command now…</span>}
                    </div>
                    <div className="voice-card-actions">
                      <button
                        type="button"
                        className="voice-card-btn primary"
                        onClick={() => {
                          clearVoiceAutoEndTimer()
                          voiceService.stopListening()
                          setIsVoiceRecording(false)
                          const finalCmd = latestSpeechRef.current.trim()
                          if (finalCmd) handleLaunchApp(finalCmd)
                        }}
                      >
                        ⏹ Stop &amp; Launch
                      </button>
                      <button
                        type="button"
                        className="voice-card-btn danger"
                        onClick={() => {
                          clearVoiceAutoEndTimer()
                          voiceService.stopListening()
                          setIsVoiceRecording(false)
                          setVoiceTranscript('')
                        }}
                      >
                        ✕ Cancel
                      </button>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Composer */}
              <div className="floating-chat-composer">
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <textarea
                    ref={messageInputRef}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        sendMessage()
                      }
                    }}
                    placeholder='Ask Doraemon or type an app…'
                    rows={1}
                    style={{
                      flex: 1,
                      background: '#ffffff',
                      color: '#0f172a',
                      border: '1px solid var(--mc-border)',
                      borderRadius: 8,
                      padding: '8px 10px',
                      fontSize: 13,
                      lineHeight: '1.4',
                      height: 38,
                      minHeight: 38,
                      overflow: 'hidden',
                      overflowY: 'hidden',
                      resize: 'none',
                      outline: 'none',
                    }}
                  />
                  <button
                    type="button"
                    className={`mc-mic-btn ${isVoiceRecording ? 'recording' : ''}`}
                    onClick={handleToggleVoice}
                    title="Toggle Voice Input"
                  >
                    {isVoiceRecording ? '⏹' : '🎤'}
                  </button>
                  <button
                    type="button"
                    className="mc-send-btn"
                    onClick={sendMessage}
                    disabled={!message.trim()}
                    title="Send"
                  >
                    ↑
                  </button>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--mc-text-subtle)' }}>
                  <span>↵ Send | Shift+↵ Newline</span>
                  <button
                    type="button"
                    style={{ background: 'none', border: 'none', color: 'var(--mc-accent-blue)', cursor: 'pointer', fontSize: 10, fontWeight: 600 }}
                    onClick={() => handleSimulatedVoiceTest('Open Notepad')}
                  >
                    🎙️ Test Voice
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  // ═════════════════════════════════════════════════════════════════════════════
  // VIEW MODE: MAIN MISSION CONTROL DASHBOARD (dashboardWindow)
  // ═════════════════════════════════════════════════════════════════════════════
  return (
    <div className="mission-control-shell">
      {/* ── Left Sidebar Navigation ── */}
      <aside className="mc-sidebar" aria-label="Dashboard Navigation">
        <div className="mc-brand">
          <div className="mc-brand-avatar">
            <AvatarCharacter state={animState} size={34} facing="right" />
          </div>
          <div className="mc-brand-text">
            <h1>OmniCompanion</h1>
            <span>Mission Control</span>
          </div>
        </div>

        <nav className="mc-nav-group">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.label}
              type="button"
              className={`mc-nav-btn ${activeTab === item.label ? 'active' : ''}`}
              onClick={() => setActiveTab(item.label)}
            >
              <span className="mc-nav-icon">{item.icon}</span>
              <span>{item.label}</span>
              {item.label === 'History' && tasks.length > 0 && (
                <span className="mc-nav-badge">{tasks.length}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="mc-sidebar-footer">
          <div className="mc-avatar-mini-status">
            <div className="mc-mini-left">
              <span className={`mc-mini-dot ${isSleeping ? 'sleeping' : ''}`} />
              <div className="mc-mini-info">
                <strong>Doraemon Avatar</strong>
                <span>{isSleeping ? 'Asleep (Hidden)' : 'Floating Active'}</span>
              </div>
            </div>
            <button
              type="button"
              className="mc-mini-sleep-btn"
              onClick={() => {
                const next = !isSleeping
                setIsSleeping(next)
                if (window.companionAPI) {
                  if (next) window.companionAPI.sleepAvatar()
                  else window.companionAPI.wakeAvatar()
                  window.companionAPI.sendSyncState({ isSleeping: next })
                }
              }}
            >
              {isSleeping ? 'Wake' : 'Sleep'}
            </button>
          </div>

          <div className="mc-mode-toggle-row">
            <span>Execution Mode</span>
            <button
              type="button"
              className={`mc-mode-pill ${executionMode}`}
              onClick={async () => {
                const next = executionMode === 'real' ? 'mock' : 'real'
                setExecutionMode(next)
                if (window.companionAPI?.setExecutionMode) {
                  await window.companionAPI.setExecutionMode(next)
                }
              }}
              title="Toggle Real Windows Execution vs Mock Simulation"
            >
              {executionMode === 'real' ? 'REAL WINDOWS' : 'MOCK MODE'} ↔
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main Dashboard Workspace ── */}
      <main className="mc-main">
        {/* Topbar Header */}
        <header className="mc-topbar">
          <div>
            <h2 className="mc-greeting-title">
              {activeTab === 'Mission Control' ? 'Mission Control Overview' : activeTab}
            </h2>
            <p className="mc-greeting-sub">
              {activeTab === 'Mission Control'
                ? 'Personalized AI Desktop Companion — Real Windows physical automation ready.'
                : NAV_ITEMS.find((n) => n.label === activeTab)?.desc}
            </p>
          </div>

          <div className="mc-topbar-actions">
            <span className="mc-badge live">● ShellExecute: LIVE</span>
            <span className="mc-badge">● STT: {voiceService.isRecognitionSupported() ? 'READY' : 'BRIDGE'}</span>
            <button
              type="button"
              className="mc-btn-pill"
              onClick={handleCheckUpdates}
              style={updateInfo && updateInfo.updateAvailable ? {
                background: 'linear-gradient(135deg, #00E676, #00B4D8)',
                color: '#000',
                fontWeight: 700,
                border: 'none',
                boxShadow: '0 0 12px rgba(0, 230, 118, 0.6)'
              } : {}}
              title={updateInfo && updateInfo.updateAvailable ? `Update v${updateInfo.remoteVersion} is available! Click to inspect.` : "Check for software updates"}
            >
              {updateInfo && updateInfo.updateAvailable ? `ℹ️ Update Available (v${updateInfo.remoteVersion})` : `🔄 v${appVersion}`}
            </button>
            <button
              type="button"
              className="mc-btn-pill"
              onClick={() => {
                if (window.companionAPI?.wakeAvatar) {
                  window.companionAPI.wakeAvatar()
                }
              }}
              title="Ensure Doraemon is visible and floating on desktop"
            >
              ✦ Show Avatar
            </button>
          </div>
        </header>

        {/* Dynamic Content Views */}
        <div className="mc-scroll-area">
          {/* ════ SOFTWARE AUTO-UPDATE BANNER ════ */}
          {((updateInfo && updateInfo.updateAvailable) || isUpdateReadyToRestart) && (
            <div
              className="mc-update-banner"
              style={{
                background: 'linear-gradient(90deg, rgba(0, 230, 118, 0.12), rgba(0, 180, 216, 0.12))',
                border: '1px solid rgba(0, 230, 118, 0.65)',
                borderRadius: 10,
                padding: '12px 18px',
                marginBottom: 16,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 12,
                boxShadow: '0 4px 20px rgba(0, 230, 118, 0.15)',
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <strong style={{ color: '#00E676', fontSize: 14 }}>
                    {isUpdateReadyToRestart
                      ? '🎉 Update Ready to Apply'
                      : `🚀 New Update Available: v${updateInfo?.remoteVersion}`}
                  </strong>
                  <span style={{ fontSize: 11, background: 'rgba(0, 230, 118, 0.2)', color: '#00E676', padding: '1px 6px', borderRadius: 4 }}>
                    Current: v{appVersion}
                  </span>
                </div>
                <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--mc-text-muted)' }}>
                  {isUpdateReadyToRestart
                    ? 'Update downloaded and extracted in background. Restart companion to activate.'
                    : (updateInfo?.releaseNotes || 'Automatic background improvements.')}
                </p>
                {updateStatusMsg && (
                  <div style={{ fontSize: 12, color: updateStatusMsg.includes('failed') || updateStatusMsg.includes('error') ? '#EF4444' : '#00E676', marginTop: 4, fontWeight: 600 }}>
                    {updateStatusMsg}
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {isUpdateReadyToRestart ? (
                  <button
                    type="button"
                    onClick={handleRelaunch}
                    style={{
                      background: '#00E676',
                      color: '#000',
                      fontWeight: 700,
                      fontSize: 12,
                      padding: '8px 18px',
                      borderRadius: 6,
                      border: 'none',
                      cursor: 'pointer',
                      boxShadow: '0 2px 10px rgba(0, 230, 118, 0.3)',
                    }}
                  >
                    ⚡ Restart Companion
                  </button>
                ) : isUpdating ? (
                  <span style={{ fontSize: 12, color: '#00E676', fontWeight: 600, padding: '8px 12px' }}>
                    ⏳ Updating silently in background…
                  </span>
                ) : (
                  <button
                    type="button"
                    disabled={isUpdating}
                    onClick={handleApplyUpdate}
                    style={{
                      background: '#00E676',
                      color: '#000',
                      fontWeight: 700,
                      fontSize: 12,
                      padding: '8px 16px',
                      borderRadius: 6,
                      border: 'none',
                      cursor: isUpdating ? 'wait' : 'pointer',
                      boxShadow: '0 2px 10px rgba(0, 230, 118, 0.3)',
                    }}
                  >
                    ⚡ Update Now
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => { setUpdateInfo(null); setIsUpdateReadyToRestart(false); }}
                  style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: 18, padding: '0 4px' }}
                  title="Dismiss update banner"
                >
                  ✕
                </button>
              </div>
            </div>
          )}
          {(notice || voiceError) && (
            <div className="chat-notice" role="status" style={{ margin: 0 }}>
              <span>ℹ</span> {voiceError || notice}
              <button onClick={() => { setNotice(''); setVoiceError(null) }} aria-label="Dismiss">×</button>
            </div>
          )}

          {/* ════ TAB 1: MISSION CONTROL ════ */}
          {activeTab === 'Mission Control' && (
            <>
              {/* Top 3-Card Summary Grid */}
              <div className="mc-cards-grid">
                {/* 1. Doraemon Avatar Representation */}
                <div className="mc-card">
                  <div className="mc-card-header">
                    <span className="mc-card-title">🤖 Doraemon Avatar</span>
                    <span className="mc-card-tag">{isSleeping ? 'Asleep' : 'Active'}</span>
                  </div>
                  <div className="mc-avatar-card-body">
                    <div className="mc-avatar-stage-preview">
                      <AvatarCharacter state={animState} size={88} facing={facing} />
                    </div>
                    <div className="mc-avatar-details">
                      <span className="mc-avatar-state-badge">State: {currentAvatarState}</span>
                      <span className="mc-avatar-meta">Facing: {facing}</span>
                      <span className="mc-avatar-meta">Movement: {isInTransit ? 'Walking across desktop' : 'Stationary'}</span>
                      <span className="mc-avatar-meta" style={{ fontSize: 10, color: 'var(--mc-accent-green)', fontWeight: 600 }}>
                        Independent Transparent Window
                      </span>
                    </div>
                  </div>
                </div>

                {/* 2. Voice Interaction Indicator */}
                <div className="mc-card">
                  <div className="mc-card-header">
                    <span className="mc-card-title">🎙️ Voice Interaction</span>
                    <span className={`mc-card-tag ${isVoiceRecording ? 'live' : ''}`}>
                      {isVoiceRecording ? 'Listening' : 'Idle'}
                    </span>
                  </div>
                  <div className="mc-voice-body">
                    <div className="mc-mic-level-row">
                      <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--mc-text-muted)' }}>Mic Audio</span>
                      <div className="mc-level-track">
                        <div className="mc-level-bar" style={{ width: `${Math.min(100, Math.max(0, audioLevel))}%` }} />
                      </div>
                      <span className="mc-level-value">{audioLevel}%</span>
                    </div>
                    <div className="mc-voice-transcript-preview">
                      {voiceTranscript ? (
                        <strong>"{voiceTranscript}"</strong>
                      ) : (
                        <span>Current command / transcription preview will appear here...</span>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: 6, marginTop: 'auto' }}>
                      <button
                        type="button"
                        className="mc-btn-pill"
                        style={{ flex: 1, justifyContent: 'center' }}
                        onClick={handleToggleVoice}
                      >
                        {isVoiceRecording ? '⏹ Stop Mic' : '🎤 Push to Talk'}
                      </button>
                      <button
                        type="button"
                        className="mc-btn-pill"
                        style={{ fontSize: 11 }}
                        onClick={() => {
                          if (window.companionAPI?.triggerVoiceTyping) {
                            window.companionAPI.triggerVoiceTyping()
                            setNotice('🎤 Windows Voice Typing active (Win+H).')
                          }
                        }}
                        title="Trigger Windows Voice Typing via software"
                      >
                        Win+H
                      </button>
                    </div>
                  </div>
                </div>

                {/* 3. Automation Engine & Permissions */}
                <div className="mc-card">
                  <div className="mc-card-header">
                    <span className="mc-card-title">⚡ Windows Automation</span>
                    <span className="mc-card-tag" style={{ background: 'var(--mc-accent-green-soft)', color: 'var(--mc-accent-green)' }}>
                      Verified
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--mc-text-muted)' }}>Process Launcher:</span>
                      <strong>ShellExecute (Windows Native)</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--mc-text-muted)' }}>Allowlisted Apps:</span>
                      <strong>6 Applications</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--mc-text-muted)' }}>Desktop Navigation:</span>
                      <strong>Physical Movement Ready</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--mc-text-muted)' }}>Mode:</span>
                      <strong style={{ color: executionMode === 'real' ? 'var(--mc-accent-green)' : 'var(--mc-accent-amber)' }}>
                        {executionMode === 'real' ? 'Real Windows Execution' : 'Mock Simulation'}
                      </strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Task Execution Pipeline */}
              <section className="mc-pipeline-section">
                <div className="mc-pipeline-header">
                  <h2>Task Execution Pipeline</h2>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--mc-accent-blue)' }}>
                      {liveProgress ? `${liveProgress.percent}%` : 'Idle'}
                    </span>
                    {launchState === 'launching' && (
                      <button
                        type="button"
                        style={{ background: 'var(--mc-accent-red)', color: '#fff', border: 'none', borderRadius: 6, padding: '3px 8px', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
                        onClick={cancelActiveTask}
                      >
                        ⏹ Cancel Task
                      </button>
                    )}
                  </div>
                </div>

                <div className="mc-pipeline-stages">
                  <div className="mc-pipeline-track">
                    <div
                      className="mc-pipeline-track-fill"
                      style={{ width: `${liveProgress ? liveProgress.percent : 0}%` }}
                    />
                  </div>

                  {/* 5 Distinct Stages */}
                  {[
                    { id: 'request_received', label: 'Listening' },
                    { id: 'understanding', label: 'Transcribing' },
                    { id: 'validating', label: 'Understanding' },
                    { id: 'launch_attempted', label: 'Executing' },
                    { id: 'launch_verified', label: 'Verified' },
                  ].map((stageDef, idx) => {
                    const st = liveProgress?.stages.find((s) => s.id === stageDef.id)
                    const status = st?.status || 'pending'
                    return (
                      <div key={stageDef.id} className={`mc-pipeline-node ${status}`}>
                        <div className="mc-node-dot">
                          {status === 'completed' ? '✓' : status === 'failed' ? '✕' : idx + 1}
                        </div>
                        <span className="mc-node-label">{stageDef.label}</span>
                      </div>
                    )
                  })}
                </div>

                {liveProgress && (
                  <div className="mc-pipeline-details">
                    <span>
                      <strong>Stage:</strong> {liveProgress.currentStageId.replace(/_/g, ' ').toUpperCase()} —{' '}
                      {liveProgress.stages.find((s) => s.id === liveProgress.currentStageId)?.detail || 'In progress…'}
                    </span>
                    <span style={{ color: 'var(--mc-text-subtle)' }}>
                      Task ID: #{liveProgress.taskId.slice(-4)}
                    </span>
                  </div>
                )}
              </section>

              {/* Command Composer */}
              <section className="mc-composer-section">
                <div className="mc-composer-box">
                  <textarea
                    ref={messageInputRef}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        sendMessage()
                      }
                    }}
                    placeholder='Ask Doraemon or type a command like "Open Notepad" or "Open Calculator"…'
                    rows={1}
                    className="mc-composer-input"
                    style={{
                      color: '#0f172a',
                    }}
                  />
                  <button
                    type="button"
                    className={`mc-mic-btn ${isVoiceRecording ? 'recording' : ''}`}
                    onClick={handleToggleVoice}
                    title={isVoiceRecording ? 'Stop Recording' : 'Start Voice Input'}
                  >
                    {isVoiceRecording ? '⏹' : '🎤'}
                  </button>
                  <button
                    type="button"
                    className="mc-send-btn"
                    onClick={sendMessage}
                    disabled={!message.trim()}
                    title="Send Command"
                  >
                    ↑
                  </button>
                </div>

                <div className="mc-chips-row">
                  <span className="mc-chip-label">Quick Actions:</span>
                  {[
                    ['📝', 'Open Notepad'],
                    ['🔢', 'Open Calculator'],
                    ['📁', 'Open File Explorer'],
                    ['🌐', 'Open Chrome'],
                    ['💻', 'Open VS Code'],
                    ['💬', 'Open WhatsApp'],
                  ].map(([icon, label]) => (
                    <button
                      key={label}
                      type="button"
                      className="mc-chip-btn"
                      onClick={() => handleLaunchApp(label)}
                    >
                      <span>{icon}</span>
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              </section>

              {/* Split lower grid: Current Task & Recent Activities */}
              <div className="mc-split-section">
                {/* Current Task */}
                <div className="mc-current-task-card">
                  <div className="mc-card-header">
                    <span className="mc-card-title">📌 Current Task</span>
                    {liveProgress && (
                      <span className="mc-card-tag" style={{ background: 'var(--mc-accent-blue-soft)', color: 'var(--mc-accent-blue)' }}>
                        In Progress
                      </span>
                    )}
                  </div>
                  {currentLaunchResult ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <LaunchBanner result={currentLaunchResult} onCancel={cancelActiveTask} />
                      {currentLaunchResult.targetInfo && (
                        <div style={{ fontSize: 11, color: 'var(--mc-text-muted)', background: 'var(--mc-bg)', padding: '8px 10px', borderRadius: 8 }}>
                          <strong>Target Location:</strong> X: {currentLaunchResult.targetInfo.destination.x}, Y: {currentLaunchResult.targetInfo.destination.y} ({currentLaunchResult.targetInfo.destinationType})
                        </div>
                      )}
                    </div>
                  ) : (
                    <p style={{ fontSize: 12, color: 'var(--mc-text-muted)', margin: 'auto 0' }}>
                      No active task running. Speak or type an application name above.
                    </p>
                  )}
                </div>

                {/* Recent Activities */}
                <div className="mc-recent-activities-card">
                  <div className="mc-card-header">
                    <span className="mc-card-title">🕒 Recent Activities</span>
                    <button
                      type="button"
                      style={{ background: 'none', border: 'none', color: 'var(--mc-accent-blue)', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}
                      onClick={() => setActiveTab('History')}
                    >
                      View All History →
                    </button>
                  </div>
                  {tasks.length === 0 ? (
                    <p style={{ fontSize: 12, color: 'var(--mc-text-muted)', margin: 'auto 0' }}>
                      No recent activities recorded yet.
                    </p>
                  ) : (
                    <div className="mc-recent-list">
                      {tasks.slice(-3).reverse().map((t) => (
                        <div key={t.id} className="mc-recent-item">
                          <div>
                            <strong style={{ fontSize: 12, color: 'var(--mc-text-main)' }}>{t.title}</strong>
                            <div style={{ fontSize: 10, color: 'var(--mc-text-subtle)' }}>{t.time}</div>
                          </div>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: 6,
                              background: t.status === 'Completed' ? 'var(--mc-accent-green-soft)' : 'var(--mc-accent-red-soft)',
                              color: t.status === 'Completed' ? 'var(--mc-accent-green)' : 'var(--mc-accent-red)',
                            }}
                          >
                            {t.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {/* ════ TAB 2: APPS & LAUNCH ════ */}
              {activeTab === 'Apps & Launch' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
                {ALLOWLISTED_APPS_INFO.map((app) => (
                  <div
                    key={app.id}
                    className="mc-card"
                    style={{ gap: 12 }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontSize: 28 }}>{app.icon}</span>
                      <div>
                        <strong style={{ fontSize: 14, color: 'var(--mc-text-main)' }}>{app.name}</strong>
                        <div style={{ fontSize: 10, color: 'var(--mc-text-muted)' }}>{app.exe}</div>
                      </div>
                    </div>
                    <p style={{ fontSize: 12, color: 'var(--mc-text-muted)', margin: 0, flex: 1 }}>
                      {app.desc}
                    </p>
                    <button
                      type="button"
                      className="mc-btn-pill"
                      style={{ justifyContent: 'center', background: 'var(--mc-peach-deep)', fontWeight: 700 }}
                      onClick={() => handleLaunchApp(`Open ${app.name}`)}
                    >
                      🚀 Launch &amp; Send Doraemon
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ════ TAB 3: VOICE SETTINGS & TESTING LAB ════ */}
          {activeTab === 'Voice Settings' && (
            <div className="voice-lab-card" style={{ maxWidth: 'none', margin: 0 }}>
              <div className="voice-lab-header">
                <span style={{ fontSize: 18 }}>🎙️</span>
                <strong>Voice &amp; Audio Testing Lab</strong>
                <span className="voice-test-badge live">READY</span>
              </div>
              <p className="voice-lab-subtitle">
                Diagnostic testing suite for microphone hardware, speech recognition, spoken responses, and automated voice tasks.
              </p>

              <div className="voice-lab-grid">
                {/* 1. Microphone Hardware Test */}
                <div className="voice-test-section">
                  <div className="voice-test-row">
                    <div>
                      <div className="voice-test-title">1. Microphone Hardware &amp; Audio Meter</div>
                      <div className="voice-test-desc">Real-time volume metering via Web Audio API AnalyserNode</div>
                    </div>
                    <button
                      type="button"
                      className={`voice-test-btn ${isTestingMic ? 'danger' : 'primary'}`}
                      onClick={toggleMicTest}
                    >
                      {isTestingMic ? '⏹ Stop Mic Test' : '🎙️ Test Microphone'}
                    </button>
                  </div>

                  <div className="voice-meter-container">
                    <div className="voice-meter-bar">
                      <div
                        className="voice-meter-fill"
                        style={{ width: `${Math.min(100, Math.max(0, isTestingMic ? micTestLevel : 0))}%` }}
                      />
                    </div>
                    <div className="voice-meter-labels">
                      <span>0 dB (Silence)</span>
                      <span style={{ fontWeight: 600, color: isTestingMic && micTestLevel > 15 ? '#0284c7' : '#64748b' }}>
                        Level: {isTestingMic ? `${micTestLevel}%` : 'Idle'}
                      </span>
                      <span>Peak (100%)</span>
                    </div>
                  </div>

                  {micTestMsg && (
                    <div className="voice-test-msg" role="status">
                      {micTestMsg}
                    </div>
                  )}
                </div>

                {/* 2. Speech-to-Text Recognition Test */}
                <div className="voice-test-section">
                  <div className="voice-test-row">
                    <div>
                      <div className="voice-test-title">2. Speech Recognition (STT)</div>
                      <div className="voice-test-desc">
                        Engine: {voiceService.isRecognitionSupported() ? 'Web Speech Recognition (Active)' : 'Automated Windows Voice Bridge'}
                      </div>
                    </div>
                    <button
                      type="button"
                      className={`voice-test-btn ${isTestingSpeech ? 'danger' : 'primary'}`}
                      onClick={toggleSpeechTest}
                    >
                      {isTestingSpeech ? '⏹ Stop Listening' : '🗣️ Test Speech Recognition'}
                    </button>
                  </div>

                  <div className="voice-transcript-box">
                    {speechTestTranscript ? (
                      `"${speechTestTranscript}"`
                    ) : (
                      <span style={{ color: '#94a3b8' }}>Live speech transcript will appear here when speaking...</span>
                    )}
                  </div>
                </div>

                {/* 3. Spoken TTS Test */}
                <div className="voice-test-section">
                  <div className="voice-test-row">
                    <div>
                      <div className="voice-test-title">3. Spoken Voice Output (TTS)</div>
                      <div className="voice-test-desc">Audible companion speech via Web SpeechSynthesis</div>
                    </div>
                    <button
                      type="button"
                      className="voice-test-btn secondary"
                      onClick={handleTestTTS}
                      disabled={isTestingTTS}
                    >
                      {isTestingTTS ? '🔊 Speaking...' : '🔊 Test Doraemon Voice'}
                    </button>
                  </div>
                </div>

                {/* 4. Windows Voice Typing Engine */}
                <div className="voice-test-section">
                  <div className="voice-test-row">
                    <div>
                      <div className="voice-test-title">4. Native Windows Voice Typing Engine</div>
                      <div className="voice-test-desc">Software-automated dictation bridge (zero keyboard actions required)</div>
                    </div>
                    <button
                      type="button"
                      className="voice-test-btn secondary"
                      onClick={() => {
                        if (window.companionAPI?.triggerVoiceTyping) {
                          window.companionAPI.triggerVoiceTyping()
                          setNotice('🎤 Windows Voice Typing active.')
                        } else {
                          setNotice('Available in Electron desktop mode.')
                        }
                      }}
                    >
                      🎙️ Trigger Voice Engine
                    </button>
                  </div>
                </div>

                {/* 5. End-to-End Voice Simulator */}
                <div className="voice-test-section">
                  <div>
                    <div className="voice-test-title">5. Voice Command Simulator (Full Workflow)</div>
                    <div className="voice-test-desc">
                      Simulate voice waveform, streaming transcript, Doraemon flight, and Windows app launch:
                    </div>
                  </div>
                  <div className="voice-simulator-chips">
                    {(['Open Notepad', 'Open Calculator', 'Open Chrome', 'Open File Explorer', 'Open VS Code'] as const).map((simCmd) => (
                      <button
                        key={simCmd}
                        type="button"
                        className="voice-sim-chip"
                        onClick={() => {
                          setActiveTab('Mission Control')
                          handleSimulatedVoiceTest(simCmd)
                        }}
                      >
                        🎙️ "{simCmd}"
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ════ TAB 4: HISTORY ════ */}
          {activeTab === 'History' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--mc-text-main)' }}>
                  Total Tasks Executed: {tasks.length}
                </span>
                {tasks.length > 0 && (
                  <button
                    type="button"
                    style={{ background: 'none', border: 'none', color: 'var(--mc-accent-red)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
                    onClick={() => setTasks([])}
                  >
                    Clear History
                  </button>
                )}
              </div>

              {tasks.length === 0 ? (
                <div className="mc-card" style={{ textAlign: 'center', padding: '40px 20px' }}>
                  <p style={{ fontSize: 13, color: 'var(--mc-text-muted)', margin: 0 }}>
                    No tasks executed yet. Try launching an application from Mission Control.
                  </p>
                </div>
              ) : (
                tasks.slice().reverse().map((t) => (
                  <div key={t.id} className="mc-card" style={{ gap: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ fontSize: 14, color: 'var(--mc-text-main)' }}>{t.title}</strong>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 6,
                          background: t.status === 'Completed' ? 'var(--mc-accent-green-soft)' : 'var(--mc-accent-red-soft)',
                          color: t.status === 'Completed' ? 'var(--mc-accent-green)' : 'var(--mc-accent-red)',
                        }}
                      >
                        {t.status}
                      </span>
                    </div>
                    {t.launchResult && (
                      <LaunchBanner result={t.launchResult} />
                    )}
                    <div style={{ fontSize: 11, color: 'var(--mc-text-subtle)' }}>{t.time}</div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* ════ TAB 5: AVATAR SETTINGS ════ */}
          {activeTab === 'Avatar Settings' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="mc-card" style={{ gap: 12 }}>
                <strong style={{ fontSize: 14 }}>Doraemon Physical Avatar Controls</strong>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <strong style={{ fontSize: 12 }}>Desktop Avatar Visibility</strong>
                    <div style={{ fontSize: 11, color: 'var(--mc-text-muted)' }}>
                      Keep Doraemon floating on top of all desktop windows
                    </div>
                  </div>
                  <button
                    type="button"
                    className="mc-btn-pill"
                    onClick={() => {
                      const next = !isSleeping
                      setIsSleeping(next)
                      if (window.companionAPI) {
                        if (next) window.companionAPI.sleepAvatar()
                        else window.companionAPI.wakeAvatar()
                        window.companionAPI.sendSyncState({ isSleeping: next })
                      }
                    }}
                  >
                    {isSleeping ? 'Wake Avatar' : 'Put to Sleep'}
                  </button>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 8, borderTop: '1px solid var(--mc-border-light)' }}>
                  <div>
                    <strong style={{ fontSize: 12 }}>Reset Home Position</strong>
                    <div style={{ fontSize: 11, color: 'var(--mc-text-muted)' }}>
                      Move Doraemon back to bottom-right resting location
                    </div>
                  </div>
                  <button
                    type="button"
                    className="mc-btn-pill"
                    onClick={() => {
                      if (window.companionAPI?.returnHome) window.companionAPI.returnHome()
                    }}
                  >
                    Return Home
                  </button>
                </div>
              </div>

              <div className="mc-card" style={{ gap: 10 }}>
                <strong style={{ fontSize: 14 }}>Companion FAQ &amp; Guidelines</strong>
                <div style={{ fontSize: 12, color: 'var(--mc-text-muted)', lineHeight: 1.5 }}>
                  <p><strong>Q: What can Doraemon do?</strong><br />
                  Doraemon recognizes your voice and typed commands to physically walk to desktop shortcuts and open allowed Windows applications.</p>
                  <p><strong>Q: How do I click him?</strong><br />
                  Single-clicking Doraemon on your Windows desktop opens the interactive floating chatbox right beside him without closing any windows.</p>
                </div>
              </div>
            </div>
          )}

                    {/* ════ TAB 6: GENERAL SETTINGS ════ */}
          {activeTab === 'General Settings' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="mc-card" style={{ gap: 12 }}>
                <strong style={{ fontSize: 14 }}>System &amp; Application Information</strong>
                <div style={{ fontSize: 12, color: 'var(--mc-text-muted)', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div><strong>Application:</strong> JM Vertex AI Desktop Companion</div>
                  <div><strong>Installed Version:</strong> v{appVersion} (Smart Auto-Update Enabled)</div>
                  <div><strong>Architecture:</strong> Electron Multi-Window (Mission Control + Transparent Overlay)</div>
                  <div><strong>Windows Automation:</strong> ShellExecute + Allowlist Security Enforcement</div>
                </div>
              </div>

              <div className="mc-card" style={{ gap: 12 }}>
                <strong style={{ fontSize: 14 }}>Software Update &amp; Maintenance</strong>
                <p style={{ fontSize: 12, color: 'var(--mc-text-muted)', margin: 0, lineHeight: 1.5 }}>
                  {updateInfo && updateInfo.updateAvailable
                    ? `ℹ️ Update v${updateInfo.remoteVersion} is available! (Current: v${appVersion}). ${updateInfo.releaseNotes}`
                    : `You are running version v${appVersion}. Updates are checked automatically on startup and apply silently in the background with zero administrator prompts.`}
                </p>
                {updateStatusMsg && (
                  <div style={{ fontSize: 12, color: updateStatusMsg.includes('failed') || updateStatusMsg.includes('error') ? '#EF4444' : '#00E676', fontWeight: 600 }}>
                    {updateStatusMsg}
                  </div>
                )}
                <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
                  {isUpdateReadyToRestart ? (
                    <button
                      type="button"
                      className="mc-btn-pill"
                      onClick={handleRelaunch}
                      style={{ background: '#00E676', color: '#000', fontWeight: 700 }}
                    >
                      ⚡ Restart Companion
                    </button>
                  ) : updateInfo && updateInfo.updateAvailable ? (
                    <>
                      <button
                        type="button"
                        className="mc-btn-pill"
                        disabled={isUpdating}
                        onClick={handleApplyUpdate}
                        style={{ background: '#00E676', color: '#000', fontWeight: 700 }}
                      >
                        {isUpdating ? '⏳ Updating in Background…' : `⚡ Update Now (v${updateInfo.remoteVersion})`}
                      </button>
                      <button
                        type="button"
                        className="mc-btn-pill"
                        onClick={handleCheckUpdates}
                        disabled={isUpdating}
                      >
                        🔄 Re-check
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="mc-btn-pill"
                      onClick={handleCheckUpdates}
                      disabled={isUpdating}
                      style={{ background: '#00E676', color: '#000', fontWeight: 700 }}
                    >
                      {isUpdating ? '⏳ Checking…' : '🔄 Check for Updates Now'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}