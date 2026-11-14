import { useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent, PointerEvent } from 'react'
import './App.css'
import './avatarAnimations.css'
import AvatarCharacter from './AvatarCharacter'
import type { AvatarAnimState } from './AvatarCharacter'
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

type Page = 'Companion' | 'Task History' | 'Settings'

/** Visual avatar state (mapped to animation state for rendering) */
type AvatarState =
  | 'Idle'
  | 'Listening'
  | 'Thinking'
  | 'Working'
  | 'Approval Required'
  | 'Greeting'
  | 'Success'
  | 'Warning'
  | 'Error'

type TaskStatus = 'Pending' | 'Stopped' | 'Completed' | 'Failed' | 'Cancelled'

type Task = {
  id: number
  title: string
  status: TaskStatus
  time?: string
  launchResult?: LaunchResult
}

type Message = {
  id: number
  author: 'You' | 'Companion'
  text: string
  time: string
  launchResult?: LaunchResult
}

// ── Constants ─────────────────────────────────────────────────────────────────

const avatarStates: AvatarState[] = [
  'Idle', 'Listening', 'Thinking', 'Working',
  'Approval Required', 'Success', 'Warning', 'Error',
]

const navigation: { label: Page; icon: string }[] = [
  { label: 'Companion', icon: '◈' },
  { label: 'Task History', icon: '◷' },
  { label: 'Settings', icon: '⚙' },
]

const GREETINGS = [
  "Hey! What shall we do today? 😊",
  "Hello! Need a little help? 🌟",
  "Hi there! Ready to explore? 🚀",
  "Hey! I'm here. What's on your mind? 💭",
]

/** Map the high-level AvatarState to an animation state for Doraemon */
function toAnimState(
  avatarState: AvatarState | string,
  isSleeping: boolean,
  launchState: LaunchState,
  isVoiceRecording: boolean,
  isInTransit: boolean = false,
  _showGreeting: boolean = false
): AvatarAnimState {
  if (isSleeping) return 'idle'
  if (isVoiceRecording) return 'listening'
  if (isInTransit || launchState === 'running' || launchState === 'launching') return 'walking'
  if (launchState === 'resolving' || launchState === 'planning') return 'thinking'
  if (launchState === 'success') return 'success'
  if (launchState === 'error' || launchState === 'failed' || launchState === 'not-allowed' || launchState === 'not-in-electron') return 'error'
  if (launchState === 'cancelled') return 'cancelled'
  switch (avatarState) {
    case 'Listening':          return 'listening'
    case 'Thinking':           return 'thinking'
    case 'Working':            return 'thinking'
    case 'Greeting':           return 'idle'
    case 'Approval Required':  return 'waiting'
    case 'Success':            return 'success'
    case 'Warning':            return 'waiting'
    case 'Error':              return 'error'
    default:                   return 'idle'
  }
}

// ── Launch banner helper ──────────────────────────────────────────────────────

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

// ── Start Menu Pinned Items ───────────────────────────────────────────────────

interface PinnedAppItem {
  icon: string
  label: string
  target: 'companion' | 'settings' | string
}

const PINNED_APPS: PinnedAppItem[] = [
  { icon: '▦', label: 'OmniCompanion', target: 'companion' },
  { icon: '📁', label: 'File Explorer', target: 'Open File Explorer' },
  { icon: '📝', label: 'Notepad', target: 'Open Notepad' },
  { icon: '🔢', label: 'Calculator', target: 'Open Calculator' },
  { icon: '🌐', label: 'Chrome', target: 'Open Chrome' },
  { icon: '⚙️', label: 'Settings', target: 'settings' },
]

const DESKTOP_SHORTCUT_TARGETS: Record<string, { x: number; y: number }> = {
  explorer: { x: 30, y: 95 },
  notepad: { x: 30, y: 185 },
  calculator: { x: 30, y: 275 },
  chrome: { x: 30, y: 365 },
  settings: { x: 30, y: 455 },
  vscode: { x: 30, y: 220 },
  whatsapp: { x: 30, y: 310 },
}

// ── App ───────────────────────────────────────────────────────────────────────

function App() {
  const [viewMode] = useState<'avatar' | 'dashboard'>(() => {
    if (typeof window === 'undefined') return 'dashboard'
    const params = new URLSearchParams(window.location.search)
    if (params.get('view') === 'avatar' || window.location.hash === '#avatar') {
      return 'avatar'
    }
    return 'dashboard'
  })

  const [message, setMessage]           = useState('')
  const [messages, setMessages]         = useState<Message[]>([])
  const [tasks, setTasks]               = useState<Task[]>([])
  const [activePage, setActivePage]     = useState<Page>('Companion')
  const [avatarState, setAvatarState]   = useState<AvatarState>('Idle')
  const [_isPaused, setIsPaused]        = useState(false)
  const [isSleeping, setIsSleeping]     = useState(false)
  const [_isAssistantPanelOpen, _setIsAssistantPanelOpen] = useState(true)
  const [isStartMenuOpen, setIsStartMenuOpen] = useState(false)
  const [desktopSearch, setDesktopSearch] = useState('')
  const [isWindowOpen, setIsWindowOpen] = useState(false)
  const [_isWindowMaximized, _setIsWindowMaximized] = useState(false)
  const [notice, setNotice]             = useState('')
  const [floatingPosition, setFloatingPosition] = useState<{ x: number; y: number } | null>(null)
  const [_windowPosition, _setWindowPosition]     = useState<{ x: number; y: number } | null>(null)
  const [currentTime, setCurrentTime]           = useState(() => new Date())
  const [showGreeting, setShowGreeting] = useState(false)
  const [greetingText, setGreetingText] = useState('')

  // ── Voice interaction state ─────────────────────────────────────────────────
  const [isVoiceRecording, setIsVoiceRecording] = useState(false)
  const [voiceTranscript, setVoiceTranscript]   = useState('')
  const [audioLevel, setAudioLevel]             = useState(0)
  const [voiceError, setVoiceError]             = useState<string | null>(null)

  // ── Voice Testing & Diagnostic state ────────────────────────────────────────
  const [isTestingMic, setIsTestingMic]                 = useState(false)
  const [micTestLevel, setMicTestLevel]                 = useState(0)
  const [micTestMsg, setMicTestMsg]                     = useState('')
  const [isTestingSpeech, setIsTestingSpeech]           = useState(false)
  const [speechTestTranscript, setSpeechTestTranscript] = useState('')
  const [isTestingTTS, setIsTestingTTS]                 = useState(false)
  const micTestCleanupRef                               = useRef<(() => void) | null>(null)

  // ── Live task progress for Mission Control ──────────────────────────────────
  const [liveProgress, setLiveProgress]         = useState<LiveTaskProgress | null>(null)
  const taskCancelledRef                        = useRef<boolean>(false)

  // ── Launch & movement state ─────────────────────────────────────────────────
  const [launchState, setLaunchState]   = useState<LaunchState>('idle')
  const [_currentLaunchResult, setCurrentLaunchResult] = useState<LaunchResult | null>(null)
  const [facing, setFacing]             = useState<'left' | 'right'>('right')
  const [executionMode, setExecutionMode] = useState<'real' | 'mock'>('real')
  const [isInTransit, setIsInTransit]   = useState(false)
  const [isDragging, setIsDragging]     = useState(false)

  const dragOrigin      = useRef<{ startX: number; startY: number; left: number; top: number; moved: boolean } | null>(null)
  const avatarDragStart = useRef<{ screenX: number; screenY: number; moved: boolean } | null>(null)
  const messageInputRef = useRef<HTMLTextAreaElement>(null)
  const voiceAutoEndTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latestSpeechRef = useRef<string>('')

  const clearVoiceAutoEndTimer = useCallback(() => {
    if (voiceAutoEndTimerRef.current) {
      clearTimeout(voiceAutoEndTimerRef.current)
      voiceAutoEndTimerRef.current = null
    }
  }, [])

  // Clock interval
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // Clean up any ongoing voice listening session or mic test on unmount
  useEffect(() => {
    return () => {
      clearVoiceAutoEndTimer()
      voiceService.stopListening()
      if (micTestCleanupRef.current) {
        micTestCleanupRef.current()
        micTestCleanupRef.current = null
      }
    }
  }, [clearVoiceAutoEndTimer])

  // ── Sync state from Electron main process ───────────────────────────────────
  useEffect(() => {
    if (viewMode === 'avatar') {
      document.documentElement.classList.add('avatar-window-mode')
      document.body.classList.add('avatar-window-mode')
    } else {
      document.documentElement.classList.remove('avatar-window-mode')
      document.body.classList.remove('avatar-window-mode')
    }

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
      })

      const cleanupMove = window.companionAPI.onMovementProgress?.((step) => {
        if (step.facing) setFacing(step.facing)
      })

      window.companionAPI.getExecutionMode?.().then((mode) => {
        if (mode) setExecutionMode(mode)
      })

      return () => {
        cleanup()
        if (cleanupMove) cleanupMove()
      }
    }
  }, [viewMode])



  // ── Cancellation Handler ────────────────────────────────────────────────────
  const cancelActiveTask = useCallback(() => {
    taskCancelledRef.current = true
    clearVoiceAutoEndTimer()

    if (isVoiceRecording) {
      voiceService.stopListening()
      setIsVoiceRecording(false)
      setAudioLevel(0)
    }

    if (window.companionAPI?.cancelMovement) {
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

    if (window.companionAPI?.returnHome) {
      setTimeout(() => {
        window.companionAPI?.returnHome()
        setAvatarState('Idle')
        setLaunchState('idle')
      }, 2500)
    }
  }, [clearVoiceAutoEndTimer, isVoiceRecording])

  // ── Helper to update Live Task Progress ─────────────────────────────────────
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

  // ── Unified App Launch & Automation Execution Flow ──────────────────────────
  const handleLaunchApp = useCallback(async (rawText: string) => {
    taskCancelledRef.current = false

    // Clear input box and voice transcript immediately so the user can type/speak again
    setMessage('')
    setVoiceTranscript('')
    latestSpeechRef.current = ''
    if (messageInputRef.current) {
      messageInputRef.current.style.height = '42px'
    }

    const now = new Date()
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    // Initialize multi-stage Live Task Progress in Mission Control
    const taskId = String(Date.now())
    const initialProgress = createInitialTaskProgress(taskId, rawText, executionMode)
    setLiveProgress(initialProgress)

    // Stage 1: Request received (completed)
    updateProgressStage('request_received', 'completed', `Received command: "${rawText}"`, 15)

    // Stage 2: Understanding request (resolving intent)
    setLaunchState('resolving')
    setAvatarState('Thinking')
    updateProgressStage('understanding', 'in_progress', 'Analyzing natural language intent…', 30)

    const intent = resolveAppIntent(rawText)
    if (!intent) {
      const errorMsg = `No recognized application found in: "${rawText}". Permitted: Notepad, Calculator, File Explorer, Chrome, VS Code, WhatsApp.`
      updateProgressStage('understanding', 'failed', errorMsg, 35)

      const result: LaunchResult = {
        state: 'not-allowed',
        displayName: rawText,
        appId: '',
        realLaunch: false,
        errorMessage: errorMsg,
      }
      setLaunchState('not-allowed')
      setCurrentLaunchResult(result)
      setAvatarState('Error')
      voiceService.speakResponse(`I could not recognize that application: ${rawText}`)

      setMessages((prev) => [
        ...prev,
        { id: Date.now(), author: 'You', text: rawText, time: timeStr },
        { id: Date.now() + 1, author: 'Companion', text: errorMsg, time: timeStr, launchResult: result },
      ])
      setTasks((prev) => [...prev, { id: Date.now() + 2, title: rawText, status: 'Failed', time: timeStr, launchResult: result }])
      setTimeout(() => { setLaunchState('idle'); setAvatarState('Idle') }, 4000)
      return
    }

    if (taskCancelledRef.current) return

    updateProgressStage('understanding', 'completed', `Identified target application: ${intent.displayName} (${intent.appId})`, 45)

    // Stage 3: Validating application against allowlist and discovering shortcut path
    updateProgressStage('validating', 'in_progress', `Validating ${intent.displayName} allowlist status…`, 55)
    await new Promise((r) => setTimeout(r, 250))

    if (taskCancelledRef.current) return
    updateProgressStage('validating', 'completed', `Validated ${intent.displayName}. Target shortcut path resolved.`, 65)

    // Stage 4: Waiting for execution & synchronizing desktop companion
    setLaunchState('planning')
    setAvatarState('Thinking')
    updateProgressStage('waiting_execution', 'in_progress', 'Preparing transparent companion coordinates…', 70)
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), author: 'You', text: rawText, time: timeStr },
    ])
    await new Promise((r) => setTimeout(r, 350))

    if (taskCancelledRef.current) return
    updateProgressStage('waiting_execution', 'completed', 'Companion positioned. Motion trajectory generated.', 75)

    // Stage 5: Launch attempted (physically traveling across Windows desktop)
    setLaunchState('launching')
    setAvatarState('Working')
    const targetCoord = DESKTOP_SHORTCUT_TARGETS[intent.appId] || { x: 30, y: 185 }
    const currentX = floatingPosition?.x ?? (typeof window !== 'undefined' ? window.innerWidth - 380 : 800)
    setFacing(targetCoord.x < currentX ? 'left' : 'right')
    setFloatingPosition(targetCoord)
    updateProgressStage('launch_attempted', 'in_progress', `Doraemon physically moving across desktop to ${intent.displayName}…`, 85)

    // Allow Doraemon to visibly fly across the desktop smoothly to the target before executing
    await new Promise((r) => setTimeout(r, 2600))
    if (taskCancelledRef.current) return

    let taskResult: import('./companion').DesktopTaskResult

    if (window.companionAPI?.startDesktopTask) {
      try {
        taskResult = await window.companionAPI.startDesktopTask({
          appId: intent.appId,
          displayName: intent.displayName,
        })
      } catch (err: unknown) {
        taskResult = {
          success: false,
          verified: false,
          displayName: intent.displayName,
          mode: executionMode,
          taskState: 'failed',
          executionMode,
          error: err instanceof Error ? err.message : String(err),
        }
      }
    } else {
      // Browser preview mode -> forward to local dev server backend
      const candidateUrls = [
        `/api/launch-app?appId=${encodeURIComponent(intent.appId)}`,
        `http://127.0.0.1:5173/api/launch-app?appId=${encodeURIComponent(intent.appId)}`,
        `http://localhost:5173/api/launch-app?appId=${encodeURIComponent(intent.appId)}`,
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
          displayName: intent.displayName,
          mode: 'real',
          taskState: 'failed',
          executionMode: 'real',
          error: lastError ? lastError.message : 'Failed to reach local launcher service.',
        }
      }
    }

    // Suppress late events if cancelled
    if (taskCancelledRef.current || taskResult.cancelled) {
      updateProgressStage('launch_verified', 'cancelled', 'Task cancelled by user before verification.', 85)
      const result: LaunchResult = {
        state: 'cancelled',
        displayName: intent.displayName,
        appId: intent.appId,
        realLaunch: false,
        cancelled: true,
        errorMessage: 'Movement cancelled by user request.',
      }
      setLaunchState('cancelled')
      setCurrentLaunchResult(result)
      setAvatarState('Error')
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          author: 'Companion',
          text: 'Movement cancelled. Doraemon stopped safely.',
          time: timeStr,
          launchResult: result,
        },
      ])
      setFloatingPosition(null)
      setFacing('right')
      setTimeout(() => { setLaunchState('idle'); setAvatarState('Idle') }, 3500)
      return
    }

    // Stage 6: Process verification
    updateProgressStage('launch_attempted', 'completed', 'Process launch command issued.', 90)

    if (taskResult.success) {
      const isMock = taskResult.mode === 'mock' || taskResult.mockSimulated
      const verifiedText = taskResult.verified
        ? 'Process verified running in Windows tasklist'
        : isMock
        ? 'Simulated in mock mode'
        : 'Process started successfully'

      updateProgressStage('launch_verified', 'completed', verifiedText, 100)

      const result: LaunchResult = {
        state: 'success',
        displayName: taskResult.displayName,
        appId: intent.appId,
        realLaunch: !isMock,
        verified: taskResult.verified,
        targetInfo: taskResult.targetInfo,
        executionMode: taskResult.executionMode,
        mockSimulated: isMock,
      }

      setLaunchState('success')
      setCurrentLaunchResult(result)
      setAvatarState('Success')

      const successText = isMock
        ? `[MOCK MODE] Simulated launch of ${taskResult.displayName}. Doraemon moved across the desktop to the shortcut target.`
        : `${taskResult.displayName} opened! Doraemon traveled across the desktop and launched the application.`

      voiceService.speakResponse(`${taskResult.displayName} opened successfully.`)

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          author: 'Companion',
          text: successText,
          time: timeStr,
          launchResult: result,
        },
      ])
      setTasks((prev) => [...prev, { id: Date.now() + 2, title: rawText, status: 'Completed', time: timeStr, launchResult: result }])

      // Celebration, then return home
      setTimeout(() => {
        setLaunchState('idle')
        setAvatarState('Idle')
        setFacing('right')
        setFloatingPosition(null)
        if (window.companionAPI?.returnHome) {
          window.companionAPI.returnHome()
        }
      }, 4500)
    } else {
      const failureReason = taskResult.error ?? 'Launch verification timed out or process failed to start.'
      updateProgressStage('launch_verified', 'failed', failureReason, 90)

      const result: LaunchResult = {
        state: 'failed',
        displayName: taskResult.displayName,
        appId: intent.appId,
        realLaunch: taskResult.mode === 'real',
        errorMessage: failureReason,
        targetInfo: taskResult.targetInfo,
        executionMode: taskResult.executionMode,
      }

      setLaunchState('failed')
      setCurrentLaunchResult(result)
      setAvatarState('Error')
      voiceService.speakResponse(`Could not open ${taskResult.displayName}.`)

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          author: 'Companion',
          text: `Failed to open ${taskResult.displayName}: ${failureReason}`,
          time: timeStr,
          launchResult: result,
        },
      ])
      setTasks((prev) => [...prev, { id: Date.now() + 2, title: rawText, status: 'Failed', time: timeStr, launchResult: result }])
      setTimeout(() => {
        setLaunchState('idle')
        setAvatarState('Idle')
        setFacing('right')
        setFloatingPosition(null)
      }, 4500)
    }
  }, [executionMode, floatingPosition, updateProgressStage])

  // ── Voice Input Handler with Automatic Turn-Off ─────────────────────────────
  const handleToggleVoice = useCallback(async () => {
    // Focus the command input field immediately for dictation
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

        if (isFinal) {
          // Final recognized speech from engine -> automatically turn off voice mode and launch
          voiceService.stopListening()
          setIsVoiceRecording(false)
          setAudioLevel(0)
          setAvatarState('Thinking')
          handleLaunchApp(text)
        } else {
          // Interim speech detected -> set auto-turn-off timer (1.3s of silence)
          voiceAutoEndTimerRef.current = setTimeout(() => {
            const finalCmd = latestSpeechRef.current.trim()
            if (finalCmd) {
              voiceService.stopListening()
              setIsVoiceRecording(false)
              setAudioLevel(0)
              setAvatarState('Thinking')
              handleLaunchApp(finalCmd)
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
          // Keep recording mode active with live visualizer
          setNotice('🎤 Microphone listening... Speak your command.')
          setAvatarState('Listening')
        } else {
          setVoiceError(err.message)
          setIsVoiceRecording(false)
          setAvatarState('Error')
        }
      },
      onEnd: () => {
        if (window.companionAPI?.isElectron) return
        clearVoiceAutoEndTimer()
        setIsVoiceRecording(false)
        setAudioLevel(0)
        const pending = latestSpeechRef.current.trim()
        if (pending && launchState === 'idle') {
          setAvatarState('Thinking')
          handleLaunchApp(pending)
        } else {
          setAvatarState((prev) => (prev === 'Listening' ? 'Idle' : prev))
        }
      },
    })

    if (!started) {
      clearVoiceAutoEndTimer()
      setIsVoiceRecording(false)
      setAvatarState('Idle')
    }
  }, [clearVoiceAutoEndTimer, handleLaunchApp, isVoiceRecording, launchState])

  // ── Voice Simulation & Diagnostic Testing Handlers ──────────────────────────
  const handleSimulatedVoiceTest = useCallback(async (commandText: string) => {
    clearVoiceAutoEndTimer()
    if (isTestingMic && micTestCleanupRef.current) {
      micTestCleanupRef.current()
      micTestCleanupRef.current = null
      setIsTestingMic(false)
    }
    setVoiceError(null)
    setVoiceTranscript('')
    setIsVoiceRecording(true)
    setAvatarState('Listening')
    if (messageInputRef.current) {
      messageInputRef.current.focus()
    }

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
  }, [clearVoiceAutoEndTimer, handleLaunchApp, isTestingMic])

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

  // ── Derived avatar values ───────────────────────────────────────────────────
  const currentAvatarState = isSleeping ? 'Idle' : avatarState
  const animState = toAnimState(currentAvatarState, isSleeping, launchState, isVoiceRecording, isInTransit, showGreeting)
  const isMoving = isInTransit || launchState === 'launching' || launchState === 'running'

  const currentPos = floatingPosition || {
    x: typeof window !== 'undefined'
      ? (isWindowOpen
          ? Math.max(20, window.innerWidth - 420 - 48 - 180 - 16)
          : Math.max(20, window.innerWidth - 220))
      : 800,
    y: typeof window !== 'undefined'
      ? (isWindowOpen
          ? Math.max(60, window.innerHeight - 280)
          : Math.max(60, window.innerHeight - 260))
      : 500,
  }

  const companionStyle: CSSProperties = {
    position: 'fixed',
    left: `${currentPos.x}px`,
    top: `${currentPos.y}px`,
    right: 'auto',
    bottom: 'auto',
    zIndex: 9990,
    transition: isDragging
      ? 'none'
      : isMoving
      ? 'left 2.8s cubic-bezier(0.35, 0, 0.25, 1), top 2.8s cubic-bezier(0.35, 0, 0.25, 1)'
      : 'left 0.65s cubic-bezier(0.25, 1, 0.5, 1), top 0.65s cubic-bezier(0.25, 1, 0.5, 1)',
    pointerEvents: 'auto',
  }

  // ── Send typed message / dispatch to unified task workflow ──────────────────
  function sendMessage() {
    clearVoiceAutoEndTimer()
    if (isVoiceRecording) {
      voiceService.stopListening()
      setIsVoiceRecording(false)
      setAudioLevel(0)
    }
    const text = message.trim()
    if (!text || isSleeping) return
    setMessage('')
    if (messageInputRef.current) {
      messageInputRef.current.style.height = '42px'
    }

    if (isLaunchIntent(text)) {
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
        text: 'Request saved in this local preview. No AI planning or computer action was performed.',
        time: timeStr,
      },
    ])
    setTasks((prev) => [...prev, { id: Date.now() + 2, title: text, status: 'Pending', time: timeStr }])
    setAvatarState('Idle')
    setNotice('Request added to the local preview.')
  }

  // ── Companion drag (browser mode) ───────────────────────────────────────────

  function startNewConversation() {
    setMessages([])
    setTasks([])
    setLiveProgress(null)
    setLaunchState('idle')
    setCurrentLaunchResult(null)
    setAvatarState('Idle')
    setNotice('Started a new conversation.')
  }

  function beginCompanionDrag(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return
    if ((event.target as HTMLElement).closest('button, select, input, a, option, .no-drag-region')) return
    dragOrigin.current = {
      startX: event.clientX,
      startY: event.clientY,
      left: currentPos.x,
      top: currentPos.y,
      moved: false,
    }
  }

  function moveCompanion(event: PointerEvent<HTMLDivElement>) {
    const origin = dragOrigin.current
    if (!origin) return
    const dx = event.clientX - origin.startX
    const dy = event.clientY - origin.startY
    const dist = Math.hypot(dx, dy)

    if (!origin.moved) {
      if (dist > 5) {
        origin.moved = true
        setIsDragging(true)
        try { event.currentTarget.setPointerCapture(event.pointerId) } catch { /* ok */ }
      } else {
        return
      }
    }

    setFloatingPosition({
      x: Math.max(10, Math.min(window.innerWidth - 190, origin.left + dx)),
      y: Math.max(10, Math.min(window.innerHeight - 240, origin.top + dy)),
    })
  }

  function endCompanionDrag(event: PointerEvent<HTMLDivElement>) {
    const origin = dragOrigin.current
    if (origin) {
      const wasMoved = origin.moved
      setIsDragging(false)
      try { event.currentTarget.releasePointerCapture(event.pointerId) } catch { /* ok */ }
      dragOrigin.current = null

      if (!wasMoved) {
        // Pointer was clicked without moving -> open/toggle chatbox!
        handleAvatarClick()
      }
    }
  }

  function nudgeCompanion(event: KeyboardEvent<HTMLDivElement>) {
    const step = 20
    const defaultX = isWindowOpen ? Math.max(12, window.innerWidth - 680) : Math.max(12, window.innerWidth - 220)
    const defaultY = Math.max(12, window.innerHeight - 300)
    const left = floatingPosition?.x ?? defaultX
    const top  = floatingPosition?.y ?? defaultY
    const moves: Record<string, { x: number; y: number }> = {
      ArrowLeft:  { x: -step, y: 0 },
      ArrowRight: { x:  step, y: 0 },
      ArrowUp:    { x: 0, y: -step },
      ArrowDown:  { x: 0, y:  step },
    }
    const move = moves[event.key]
    if (!move) return
    event.preventDefault()
    setFloatingPosition({
      x: Math.max(10, Math.min(window.innerWidth - 190, left + move.x)),
      y: Math.max(10, Math.min(window.innerHeight - 240, top + move.y)),
    })
  }

  function beginAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return
    if ((event.target as HTMLElement).closest('button, select, input, a, option, .no-drag-region')) return
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

  function endAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    if (avatarDragStart.current) {
      const wasMoved = avatarDragStart.current.moved
      try { event.currentTarget.releasePointerCapture(event.pointerId) } catch { /* ok */ }
      avatarDragStart.current = null

      if (!wasMoved) {
        // Single click on Doraemon avatar in floating overlay window
        if (isSleeping) {
          setIsSleeping(false)
          if (window.companionAPI) {
            window.companionAPI.wakeAvatar()
            window.companionAPI.sendSyncState({ isSleeping: false })
          }
        } else {
          if (window.companionAPI) {
            window.companionAPI.openDashboard()
          } else {
            window.location.search = '?view=dashboard'
          }
        }
      }
    }
  }

  // ── Avatar click handler ─────────────────────────────────────────────────────
  function handleAvatarClick() {
    if (isSleeping) {
      setIsSleeping(false)
      setNotice('Companion woke up.')
      if (window.companionAPI) {
        window.companionAPI.wakeAvatar()
        window.companionAPI.sendSyncState({ isSleeping: false })
      }
      return
    }
    const greeting = GREETINGS[Math.floor(Math.random() * GREETINGS.length)]
    setGreetingText(greeting)
    setShowGreeting(true)
    setAvatarState('Greeting') // friendly greeting wave animation
    setTimeout(() => setAvatarState('Idle'), 2200)
    // Auto-dismiss the greeting bubble after 2.8 seconds
    setTimeout(() => setShowGreeting(false), 2800)

    // Toggle chatbox open/closed immediately
    setIsWindowOpen((prev) => {
      const next = !prev
      if (next) {
        setTimeout(() => messageInputRef.current?.focus(), 60)
      }
      return next
    })

    // TTS greeting when opening
    if (window.speechSynthesis && !isWindowOpen) {
      try {
        const utt = new SpeechSynthesisUtterance(greeting.replace(/[\u{1F60A}\u{1F31F}\u{1F680}\u{1F4AD}]/gu, ''))
        utt.rate = 1.1; utt.pitch = 1.1; utt.volume = 0.7
        window.speechSynthesis.speak(utt)
      } catch { /* ok */ }
    }
  }

  // ── Standalone Avatar Window (Electron floating overlay) ─────────────────────
  if (viewMode === 'avatar') {
    return (
      <div
        className={`standalone-avatar-window state-${currentAvatarState.toLowerCase().replaceAll(' ', '-')} ${isSleeping ? 'is-sleeping' : ''}`}
        role="region"
        aria-label="Floating Companion Avatar"
        onPointerDown={beginAvatarDrag}
        onPointerMove={moveAvatarDrag}
        onPointerUp={endAvatarDrag}
        onPointerCancel={endAvatarDrag}
        onDoubleClick={() => {
          if (window.companionAPI) { window.companionAPI.openDashboard() }
        }}
        title="Doraemon Desktop Companion (Double-click to open Mission Control)"
      >
        <div
          className="avatar-float-stage"
          onClick={(e) => {
            e.stopPropagation()
            if (isSleeping) {
              setIsSleeping(false)
              if (window.companionAPI) {
                window.companionAPI.wakeAvatar()
                window.companionAPI.sendSyncState({ isSleeping: false })
              }
            } else {
              if (window.companionAPI) {
                window.companionAPI.openDashboard()
              } else {
                window.location.search = '?view=dashboard'
              }
            }
          }}
          style={{ cursor: 'pointer' }}
          role="button"
          tabIndex={0}
          title="Click to open Mission Control / Chatbox"
          aria-label="Click to open Mission Control / Chatbox"
        >
          {isSleeping && (
            <div className="avatar-zzz-cloud" aria-hidden="true">
              <span className="z1">z</span>
              <span className="z2">z</span>
              <span className="z3">Z</span>
            </div>
          )}

          <div className={`avatar-image-wrapper avatar-state-${animState}`}>
            <AvatarCharacter state={animState} size={160} facing={facing} />
          </div>

          <div className="avatar-ground-shadow" aria-hidden="true" />
        </div>

        <div className="avatar-controls-dock no-drag-region" role="toolbar" aria-label="Avatar quick controls">
          <button
            type="button"
            className="avatar-control-btn active"
            onClick={(e) => {
              e.stopPropagation()
              if (window.companionAPI) { window.companionAPI.openDashboard() }
              else { window.location.search = '?view=dashboard' }
            }}
            title="Open Mission Control Dashboard"
            aria-label="Open Mission Control Dashboard"
          >
            <span className="control-icon" aria-hidden="true">✦</span>
            <span className="control-text">Dashboard</span>
          </button>

          <button
            type="button"
            className={`avatar-control-btn sleep-toggle ${isSleeping ? 'is-sleeping' : ''}`}
            onClick={(e) => {
              e.stopPropagation()
              if (isSleeping) {
                setIsSleeping(false)
                setIsPaused(false)
                if (window.companionAPI) window.companionAPI.sendSyncState({ isSleeping: false })
              } else {
                if (window.companionAPI) {
                  window.companionAPI.sleepAvatar()
                  window.companionAPI.sendSyncState({ isSleeping: true })
                } else {
                  setIsSleeping(true)
                }
              }
            }}
            title={isSleeping ? 'Wake companion' : 'Put companion to sleep (hide)'}
            aria-label={isSleeping ? 'Wake companion' : 'Put companion to sleep (hide)'}
          >
            <span className="control-icon" aria-hidden="true">{isSleeping ? '☼' : '☾'}</span>
            <span className="control-text">{isSleeping ? 'Wake' : 'Sleep'}</span>
          </button>
        </div>
      </div>
    )
  }

  // ── Windows 11 Desktop View ──────────────────────────────────────────────────
  return (
    <div className="windows-desktop">
      <div className="desktop-wallpaper-glow" aria-hidden="true" />

      {/* Desktop Shortcuts (left column) */}
      <nav className="desktop-shortcuts" aria-label="Desktop shortcuts">
        <button className="desktop-shortcut" onClick={() => { setActivePage('Companion'); setIsWindowOpen(true) }}>
          <span className="desktop-shortcut-icon companion-shortcut">✦</span><span>OmniCompanion</span>
        </button>
        <button className="desktop-shortcut" onClick={() => handleLaunchApp('Open File Explorer')}>
          <span className="desktop-shortcut-icon explorer-shortcut">📁</span><span>File Explorer</span>
        </button>
        <button className="desktop-shortcut" onClick={() => handleLaunchApp('Open Notepad')}>
          <span className="desktop-shortcut-icon notepad-shortcut">📝</span><span>Notepad</span>
        </button>
        <button className="desktop-shortcut" onClick={() => handleLaunchApp('Open Calculator')}>
          <span className="desktop-shortcut-icon calculator-shortcut">🔢</span><span>Calculator</span>
        </button>
        <button className="desktop-shortcut" onClick={() => handleLaunchApp('Open Chrome')}>
          <span className="desktop-shortcut-icon chrome-shortcut">🌐</span><span>Google Chrome</span>
        </button>
        <button className="desktop-shortcut" onClick={() => { setActivePage('Settings'); setIsWindowOpen(true) }}>
          <span className="desktop-shortcut-icon settings-shortcut">⚙️</span><span>Settings</span>
        </button>
      </nav>

      {/* Doraemon on Desktop */}
      <section
        className={`desktop-companion-stage state-${currentAvatarState.toLowerCase().replaceAll(' ', '-')} ${isSleeping ? 'is-sleeping' : ''} ${isMoving ? 'is-moving' : ''}`}
        style={companionStyle}
        role="region"
        aria-label="Floating Doraemon Companion"
        tabIndex={0}
        onPointerDown={beginCompanionDrag}
        onPointerMove={moveCompanion}
        onPointerUp={endCompanionDrag}
        onPointerCancel={endCompanionDrag}
        onKeyDown={nudgeCompanion}
      >
        {/* Greeting speech bubble */}
        {showGreeting && (
          <div className="companion-speech-bubble" role="status">
            <p>{greetingText}</p>
          </div>
        )}

        {/* Avatar (clickable) */}
        <div
          className={`avatar-float-stage avatar-state-${animState}`}
          onClick={(e) => {
            e.stopPropagation()
            handleAvatarClick()
          }}
          role="button"
          tabIndex={0}
          aria-label="Doraemon companion. Click to chat"
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              handleAvatarClick()
            }
          }}
          style={{ cursor: 'pointer' }}
        >
          {/* zzz cloud when sleeping */}
          {isSleeping && (
            <div className="avatar-zzz-cloud" aria-hidden="true">
              <span className="z1">z</span>
              <span className="z2">z</span>
              <span className="z3">Z</span>
            </div>
          )}

          <div className="avatar-image-wrapper">
            <AvatarCharacter state={animState} size={180} facing={facing} />
          </div>
          <div className="avatar-ground-shadow" aria-hidden="true" />
        </div>

        {/* Small hint text under Doraemon */}
        {!isWindowOpen && !isSleeping && (
          <div
            className="avatar-click-hint"
            onClick={(e) => {
              e.stopPropagation()
              handleAvatarClick()
            }}
            role="button"
            tabIndex={0}
            style={{ cursor: 'pointer', pointerEvents: 'auto' }}
          >
            ✦ Click to chat ✦
          </div>
        )}

        {/* Drag hint */}
        <div className="avatar-drag-hint" aria-hidden="true">
          <span>⠿</span>
          <span>Drag to move</span>
        </div>
      </section>

      {/* Chat Panel (pastel popup) */}
      {isWindowOpen && (
        <section className="chat-popup-panel" aria-label="OmniCompanion Chat">
          <header className="chat-popup-header">
            <div className="chat-popup-brand">
              <AvatarCharacter state={animState} size={48} facing="right" />
              <div>
                <strong>OmniCompanion</strong>
                <span>{isVoiceRecording ? '🎤 Listening…' : currentAvatarState}</span>
              </div>
            </div>
            <div className="chat-popup-controls">
              <button
                onClick={() => setIsWindowOpen(false)}
                aria-label="Minimize chat"
                title="Minimize"
              >−</button>
              <button
                onClick={() => setIsWindowOpen(false)}
                aria-label="Close chat"
                title="Close"
              >×</button>
            </div>
          </header>

          {/* Tab navigation */}
          <nav className="chat-popup-tabs" aria-label="Chat sections">
            {navigation.map(({ label, icon }) => (
              <button
                key={label}
                className={activePage === label ? 'active' : ''}
                aria-current={activePage === label ? 'page' : undefined}
                onClick={() => setActivePage(label)}
              >
                {icon} {label}
                {label === 'Task History' && tasks.length > 0 && (
                  <span style={{ marginLeft: 4, fontSize: 10, background: '#E8A87C', color: '#fff', borderRadius: 8, padding: '1px 5px', fontWeight: 'bold' }}>
                    {tasks.length}
                  </span>
                )}
              </button>
            ))}
          </nav>

          <div className="chat-popup-body">
            {/* ── Companion page ── */}
            {activePage === 'Companion' && (
              <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                <div className="chat-scroll-area" aria-live="polite">
                  {messages.length === 0 ? (
                    <div className="chat-welcome">
                      <h2>Hey there! 👋</h2>
                      <p>Try opening an app — speak or type a command like <em>"Open Notepad"</em> or <em>"Open Calculator"</em></p>
                      <div className="chat-suggestion-chips">
                        {[
                          ['📝', 'Open Notepad'],
                          ['🔢', 'Open Calculator'],
                          ['📁', 'Open File Explorer'],
                          ['💻', 'Open VS Code'],
                        ].map(([icon, title]) => (
                          <button
                            className="chat-chip"
                            key={title}
                            onClick={() => handleLaunchApp(title)}
                          >
                            <span aria-hidden="true">{icon}</span>
                            {title}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    messages.map((item) => (
                      <div className={`chat-message ${item.author === 'You' ? 'user' : 'companion'}`} key={item.id}>
                        <div className="chat-message-bubble">
                          {item.text}
                          {item.launchResult && (
                            <div style={{ marginTop: 6 }}>
                              <LaunchBanner result={item.launchResult} onCancel={cancelActiveTask} />
                            </div>
                          )}
                        </div>
                        <div className="chat-message-time">{item.time}</div>
                      </div>
                    ))
                  )}
                </div>

                {/* Voice recording card */}
                {(isVoiceRecording || voiceTranscript) && (
                  <div className="chat-voice-card">
                    <div className="chat-voice-header">
                      <span className="voice-recording-dot" aria-hidden="true" />
                      <span>{isVoiceRecording ? 'Listening… Speak your command' : 'Recognized Speech'}</span>
                      {isVoiceRecording && (
                        <div className="voice-waveform" aria-hidden="true" style={{ marginLeft: 'auto' }}>
                          {[1, 2, 3, 4, 5].map((barIndex) => {
                            const dynamicHeight = Math.max(4, Math.min(20, Math.round((audioLevel / 100) * 18 * (0.6 + (barIndex % 3) * 0.25))))
                            return <span key={barIndex} className="waveform-bar" style={{ height: `${dynamicHeight}px` }} />
                          })}
                        </div>
                      )}
                    </div>
                    <div className="chat-voice-transcript">
                      {voiceTranscript
                        ? `"${voiceTranscript}"`
                        : <span style={{ opacity: 0.5 }}>Listening for command…</span>
                      }
                    </div>
                    <div className="voice-card-actions">
                      {isVoiceRecording ? (
                        <>
                          <button
                            type="button"
                            className="voice-card-btn primary"
                            onClick={() => {
                              clearVoiceAutoEndTimer()
                              voiceService.stopListening()
                              setIsVoiceRecording(false)
                              setAudioLevel(0)
                              const finalCmd = latestSpeechRef.current.trim()
                              if (finalCmd) {
                                setAvatarState('Thinking')
                                handleLaunchApp(finalCmd)
                              } else {
                                setAvatarState('Idle')
                              }
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
                              setAudioLevel(0)
                              setVoiceTranscript('')
                              latestSpeechRef.current = ''
                              setAvatarState('Idle')
                            }}
                          >
                            ✕ Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="voice-card-btn primary"
                            onClick={() => {
                              if (voiceTranscript.trim()) {
                                handleLaunchApp(voiceTranscript.trim())
                              }
                            }}
                          >
                            ↵ Launch Command
                          </button>
                          <button
                            type="button"
                            className="voice-card-btn secondary"
                            onClick={handleToggleVoice}
                          >
                            ↻ Speak Again
                          </button>
                          <button
                            type="button"
                            className="voice-card-btn danger"
                            onClick={() => {
                              setVoiceTranscript('')
                              latestSpeechRef.current = ''
                            }}
                          >
                            ✕ Dismiss
                          </button>
                        </>
                      )}
                    </div>
                    <div className="voice-test-quick-chips">
                      <span className="voice-quick-chip-label">Quick Test:</span>
                      {(['Open Notepad', 'Open Calculator', 'Open Chrome', 'Open File Explorer'] as const).map((cmd) => (
                        <button
                          key={cmd}
                          type="button"
                          className="voice-quick-chip"
                          onClick={() => handleSimulatedVoiceTest(cmd)}
                          title={`Test voice input simulation: "${cmd}"`}
                        >
                          🎙️ {cmd}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Notice banner */}
                {(notice || voiceError) && (
                  <div className="chat-notice" role="status">
                    <span aria-hidden="true">ℹ</span>
                    {voiceError || notice}
                    <button
                      aria-label="Dismiss"
                      onClick={() => { setNotice(''); setVoiceError(null) }}
                    >×</button>
                  </div>
                )}

                {/* Composer */}
                <div className="chat-composer">
                  <div className="chat-composer-row">
                    <label className="sr-only" htmlFor="chat-message-input">Message your companion</label>
                    <textarea
                      id="chat-message-input"
                      ref={messageInputRef}
                      value={message}
                      onChange={(e) => {
                        const val = e.target.value
                        setMessage(val)
                        e.target.style.height = 'auto'
                        e.target.style.height = `${Math.min(120, Math.max(42, e.target.scrollHeight))}px`
                        if (isVoiceRecording) {
                          latestSpeechRef.current = val
                          setVoiceTranscript(val)
                          clearVoiceAutoEndTimer()
                          voiceAutoEndTimerRef.current = setTimeout(() => {
                            const finalCmd = latestSpeechRef.current.trim()
                            if (finalCmd) {
                              voiceService.stopListening()
                              setIsVoiceRecording(false)
                              setAudioLevel(0)
                              setAvatarState('Thinking')
                              handleLaunchApp(finalCmd)
                            }
                          }, 1300)
                        }
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          if (isVoiceRecording) {
                            clearVoiceAutoEndTimer()
                            voiceService.stopListening()
                            setIsVoiceRecording(false)
                            setAudioLevel(0)
                          }
                          sendMessage()
                          if (messageInputRef.current) {
                            messageInputRef.current.style.height = '42px'
                          }
                        }
                      }}
                      placeholder='Ask Doraemon or type "Open Notepad"…'
                      rows={1}
                      disabled={isSleeping || launchState === 'launching' || launchState === 'running'}
                    />
                    <button
                      type="button"
                      className={`chat-mic-btn ${isVoiceRecording ? 'recording' : ''}`}
                      aria-label={isVoiceRecording ? 'Stop voice recording' : 'Start voice input'}
                      title={isVoiceRecording ? 'Stop recording' : 'Speak command'}
                      onClick={handleToggleVoice}
                    >
                      {isVoiceRecording ? '⏹' : '🎤'}
                    </button>
                    <button
                      type="button"
                      className="chat-send-btn"
                      aria-label="Send message"
                      title="Send"
                      disabled={!message.trim() || isSleeping || launchState === 'launching' || launchState === 'running'}
                      onClick={() => {
                        sendMessage()
                        if (messageInputRef.current) {
                          messageInputRef.current.style.height = '42px'
                        }
                      }}
                    >
                      ↑
                    </button>
                  </div>
                  <div className="chat-composer-helper">
                    <span>↵ Send</span>
                    <span>Shift+↵ New line</span>
                    <span>🎙️ Auto-Voice</span>
                    <button
                      type="button"
                      className="helper-voice-test-btn"
                      onClick={() => handleSimulatedVoiceTest('Open Calculator')}
                      title="Run quick voice test with 'Open Calculator'"
                    >
                      🎙️ Test Voice
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ── Task History page ── */}
            {activePage === 'Task History' && (
              <div style={{ padding: '16px', overflowY: 'auto', flex: 1 }}>
                {tasks.length === 0 ? (
                  <div className="chat-welcome">
                    <h2>No tasks yet</h2>
                    <p>App launches and requests will appear here.</p>
                    <button
                      className="chat-chip"
                      onClick={() => setActivePage('Companion')}
                    >
                      ◈ Go to Chat
                    </button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {tasks.slice().reverse().map((task) => (
                      <article
                        key={task.id}
                        style={{
                          background: 'white',
                          borderRadius: 12,
                          padding: '10px 14px',
                          border: '1px solid rgba(248,220,203,0.6)',
                          boxShadow: '0 1px 4px rgba(84,72,63,0.07)',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                          <div>
                            <strong style={{ fontSize: 13, color: 'var(--warm-dark)' }}>{task.title}</strong>
                            {task.launchResult && (
                              <div style={{ marginTop: 4 }}>
                                <LaunchBanner result={task.launchResult} />
                              </div>
                            )}
                          </div>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: 10,
                              background: task.status === 'Completed' ? 'rgba(52,211,153,0.15)' : task.status === 'Failed' ? 'rgba(239,68,68,0.1)' : 'rgba(248,220,203,0.6)',
                              color: task.status === 'Completed' ? '#059669' : task.status === 'Failed' ? '#DC2626' : 'var(--warm-mid)',
                              flexShrink: 0,
                            }}
                          >
                            {task.status}
                          </span>
                        </div>
                        {task.time && <div style={{ fontSize: 10, color: 'var(--warm-light)', marginTop: 4 }}>{task.time}</div>}
                      </article>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ── Settings page ── */}
            {activePage === 'Settings' && (
              <div style={{ padding: '16px', overflowY: 'auto', flex: 1 }}>
                <div className="chat-welcome" style={{ alignItems: 'flex-start', textAlign: 'left' }}>
                  <h2>Settings</h2>
                  <p>Manage voice input, execution permissions, and companion controls.</p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {/* ── Voice & Audio Testing Lab ── */}
                  <div className="voice-lab-card">
                    <div className="voice-lab-header">
                      <span style={{ fontSize: 16 }}>🎙️</span>
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

                      {/* 3. Doraemon Spoken Voice (TTS) Test */}
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

                      {/* 5. End-to-End Voice Command Simulator */}
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
                                setActivePage('Companion')
                                handleSimulatedVoiceTest(simCmd)
                              }}
                              title={`Simulate voice command: "${simCmd}"`}
                            >
                              🎙️ "{simCmd}"
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div style={{ background: 'white', borderRadius: 12, padding: '12px 14px', border: '1px solid rgba(248,220,203,0.6)' }}>
                    <strong style={{ fontSize: 12, color: 'var(--warm-dark)', display: 'block', marginBottom: 6 }}>Windows Automation</strong>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 11, color: 'var(--warm-mid)' }}>Process verification via ShellExecute</span>
                      <span style={{ fontSize: 10, fontWeight: 700, color: '#34D399' }}>
                        {window.companionAPI?.isElectron ? 'LIVE' : 'BRIDGE READY'}
                      </span>
                    </div>
                  </div>

                  <div style={{ background: 'white', borderRadius: 12, padding: '12px 14px', border: '1px solid rgba(248,220,203,0.6)' }}>
                    <strong style={{ fontSize: 12, color: 'var(--warm-dark)', display: 'block', marginBottom: 6 }}>Launch Mode</strong>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 11, color: 'var(--warm-mid)' }}>{executionMode === 'real' ? 'Real Windows Execution' : 'Mock Simulation'}</span>
                      <button
                        style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 10, border: 'none', cursor: 'pointer', background: executionMode === 'real' ? 'rgba(52,211,153,0.15)' : 'rgba(245,158,11,0.15)', color: executionMode === 'real' ? '#059669' : '#D97706' }}
                        onClick={async () => {
                          const next = executionMode === 'real' ? 'mock' : 'real'
                          setExecutionMode(next)
                          if (window.companionAPI?.setExecutionMode) {
                            await window.companionAPI.setExecutionMode(next)
                          }
                          setNotice(`Switched to ${next === 'real' ? 'Real Windows Execution' : 'Mock Simulation'} mode.`)
                        }}
                      >
                        {executionMode === 'real' ? 'REAL' : 'MOCK'} ↔
                      </button>
                    </div>
                  </div>

                  <div style={{ background: 'white', borderRadius: 12, padding: '12px 14px', border: '1px solid rgba(248,220,203,0.6)' }}>
                    <strong style={{ fontSize: 12, color: 'var(--warm-dark)', display: 'block', marginBottom: 6 }}>Companion Sleep</strong>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 11, color: 'var(--warm-mid)' }}>{isSleeping ? 'Companion is sleeping' : 'Companion is active'}</span>
                      <button
                        style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 10, border: 'none', cursor: 'pointer', background: 'rgba(248,220,203,0.6)', color: 'var(--warm-dark)' }}
                        onClick={() => {
                          const next = !isSleeping
                          setIsSleeping(next)
                          setIsPaused(false)
                          setNotice(next ? 'Companion is asleep.' : 'Companion woke up.')
                          if (window.companionAPI) {
                            if (next) { window.companionAPI.sleepAvatar() } else { window.companionAPI.wakeAvatar() }
                            window.companionAPI.sendSyncState({ isSleeping: next })
                          }
                        }}
                      >
                        {isSleeping ? '☼ Wake' : '☾ Sleep'}
                      </button>
                    </div>
                  </div>

                  <div style={{ background: 'white', borderRadius: 12, padding: '12px 14px', border: '1px solid rgba(248,220,203,0.6)' }}>
                    <strong style={{ fontSize: 12, color: 'var(--warm-dark)', display: 'block', marginBottom: 6 }}>Allowed Apps</strong>
                    <span style={{ fontSize: 11, color: 'var(--warm-mid)' }}>Notepad, Calculator, File Explorer, Chrome, VS Code, WhatsApp</span>
                  </div>

                  <button
                    className="chat-chip"
                    style={{ marginTop: 4 }}
                    onClick={startNewConversation}
                  >
                    ＋ New Conversation
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Task status bar at bottom of chat (compact) */}
          {liveProgress && (
            <div className="chat-task-status" role="status" aria-live="polite">
              <span className="task-status-dot" aria-hidden="true" />
              <span>{liveProgress.currentStageId.replace(/_/g, ' ')}</span>
              <strong>{liveProgress.percent}%</strong>
              {liveProgress.currentStageId !== 'launch_verified'
                && liveProgress.currentStageId !== 'failed'
                && liveProgress.currentStageId !== 'cancelled' && (
                <button onClick={cancelActiveTask} aria-label="Cancel task">✕</button>
              )}
            </div>
          )}
        </section>
      )}

      {/* Start Menu */}
      {isStartMenuOpen && (
        <>
          <button className="start-menu-backdrop" aria-label="Close Start menu" onClick={() => setIsStartMenuOpen(false)} />
          <section className="windows-start-menu" aria-label="Start menu">
            <form className="start-search" onSubmit={(e) => { e.preventDefault(); const q = desktopSearch.trim(); if (q) { handleLaunchApp(q); setDesktopSearch(''); setIsStartMenuOpen(false) } }}>
              <span>⌕</span>
              <input value={desktopSearch} onChange={(e) => setDesktopSearch(e.target.value)} placeholder="Search for apps, settings, and documents" aria-label="Search" autoFocus />
              <button type="submit" aria-label="Search">↵</button>
            </form>
            <div className="start-menu-section-heading"><strong>Pinned</strong><span>All apps　›</span></div>
            <div className="start-pinned-grid">
              {PINNED_APPS.map((item) => (
                <button
                  type="button"
                  className="start-pinned-item"
                  key={item.label}
                  onClick={() => {
                    setIsStartMenuOpen(false)
                    if (item.target === 'companion') {
                      setIsWindowOpen(true)
                      setActivePage('Companion')
                    } else if (item.target === 'settings') {
                      setActivePage('Settings')
                      setIsWindowOpen(true)
                    } else {
                      handleLaunchApp(item.target)
                    }
                  }}
                >
                  <span>{item.icon}</span>
                  <small>{item.label}</small>
                </button>
              ))}
            </div>
            <div className="start-menu-section-heading recommended-heading"><strong>Recommended</strong><span>More　›</span></div>
            <div className="start-recommended"><span className="recommended-file-icon">◫</span><div><strong>Welcome to OmniCompanion</strong><small>Voice & typed desktop automation ready</small></div></div>
            <footer className="start-menu-footer"><span className="start-user-avatar">U</span><strong>Local user</strong><button title="Power" onClick={() => setIsStartMenuOpen(false)}>⏻</button></footer>
          </section>
        </>
      )}

      {/* Taskbar */}
      <footer className="windows-taskbar">
        <button className={`taskbar-start ${isStartMenuOpen ? 'taskbar-active' : ''}`} aria-label="Start" title="Start" onClick={() => setIsStartMenuOpen((v) => !v)}><span className="windows-logo"><i /><i /><i /><i /></span></button>
        <button className="taskbar-search" onClick={() => setIsStartMenuOpen(true)}><span>⌕</span><small>Search</small></button>
        <span className="taskbar-divider" />
        <button className={`taskbar-app ${isWindowOpen ? 'taskbar-app-active' : ''}`} title="OmniCompanion AI" onClick={() => setIsWindowOpen((v) => !v)}><span>✦</span></button>
        <button className="taskbar-app" title="File Explorer" onClick={() => handleLaunchApp('Open File Explorer')}>📁</button>
        <button className="taskbar-app" title="Notepad" onClick={() => handleLaunchApp('Open Notepad')}>📝</button>
        <button className="taskbar-app" title="Calculator" onClick={() => handleLaunchApp('Open Calculator')}>🔢</button>
        <button className="taskbar-app" title="Google Chrome" onClick={() => handleLaunchApp('Open Chrome')}>🌐</button>
        <button className="taskbar-app" title="Settings" onClick={() => { setActivePage('Settings'); setIsWindowOpen(true) }}>⚙️</button>
        <div className="taskbar-tray">
          <span title="Wi-Fi connected">📶</span>
          <span title="Volume 100%">🔊</span>
          <span title="Battery 100%">🔋</span>
          <div className="taskbar-clock">
            <strong>{currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong>
            <small>{currentTime.toLocaleDateString([], { month: '2-digit', day: '2-digit', year: 'numeric' })}</small>
          </div>
          <button title="Notifications" onClick={() => setNotice('You are all caught up.')}>🔔</button>
        </div>
      </footer>
    </div>
  )
}

export default App
