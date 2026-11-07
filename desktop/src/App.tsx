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

/** Map the high-level AvatarState to an animation state for Doraemon */
function toAnimState(
  avatarState: AvatarState,
  isSleeping: boolean,
  launchState: LaunchState,
  isVoiceRecording: boolean
): AvatarAnimState {
  if (isSleeping) return 'idle'
  if (isVoiceRecording) return 'listening'
  if (launchState === 'running' || launchState === 'launching') return 'running'
  if (launchState === 'resolving' || launchState === 'planning') return 'thinking'
  if (launchState === 'success') return 'success'
  if (launchState === 'error' || launchState === 'failed' || launchState === 'not-allowed' || launchState === 'not-in-electron') return 'error'
  if (launchState === 'cancelled') return 'cancelled'
  switch (avatarState) {
    case 'Listening':          return 'listening'
    case 'Thinking':           return 'thinking'
    case 'Working':            return 'thinking'
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
        {body && <span>{body}</span>}
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
  const [isPaused, setIsPaused]         = useState(false)
  const [isSleeping, setIsSleeping]     = useState(false)
  const [isAssistantPanelOpen, setIsAssistantPanelOpen] = useState(true)
  const [isStartMenuOpen, setIsStartMenuOpen] = useState(false)
  const [desktopSearch, setDesktopSearch] = useState('')
  const [isWindowOpen, setIsWindowOpen] = useState(true)
  const [isWindowMaximized, setIsWindowMaximized] = useState(false)
  const [notice, setNotice]             = useState('')
  const [floatingPosition, setFloatingPosition] = useState<{ x: number; y: number } | null>(null)
  const [windowPosition, setWindowPosition]     = useState<{ x: number; y: number } | null>(null)
  const [currentTime, setCurrentTime]           = useState(() => new Date())

  // ── Voice interaction state ─────────────────────────────────────────────────
  const [isVoiceRecording, setIsVoiceRecording] = useState(false)
  const [voiceTranscript, setVoiceTranscript]   = useState('')
  const [audioLevel, setAudioLevel]             = useState(0)
  const [voiceError, setVoiceError]             = useState<string | null>(null)

  // ── Live task progress for Mission Control ──────────────────────────────────
  const [liveProgress, setLiveProgress]         = useState<LiveTaskProgress | null>(null)
  const taskCancelledRef                        = useRef<boolean>(false)

  // ── Launch & movement state ─────────────────────────────────────────────────
  const [launchState, setLaunchState]   = useState<LaunchState>('idle')
  const [currentLaunchResult, setCurrentLaunchResult] = useState<LaunchResult | null>(null)
  const [facing, setFacing]             = useState<'left' | 'right'>('right')
  const [executionMode, setExecutionMode] = useState<'real' | 'mock'>('real')
  const [isDragging, setIsDragging]     = useState(false)

  const dragOrigin      = useRef<{ x: number; y: number; left: number; top: number } | null>(null)
  const avatarDragStart = useRef<{ x: number; y: number } | null>(null)
  const windowDragStart = useRef<{ mouseX: number; mouseY: number; startX: number; startY: number } | null>(null)
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

  // Clean up any ongoing voice listening session on unmount
  useEffect(() => {
    return () => {
      clearVoiceAutoEndTimer()
      voiceService.stopListening()
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

  // ── Window drag handlers ────────────────────────────────────────────────────
  function beginWindowDrag(e: PointerEvent<HTMLDivElement>) {
    if (isWindowMaximized) return
    if ((e.target as HTMLElement).closest('button, input, select, textarea, a')) return
    const frame = (e.currentTarget.parentElement as HTMLElement)?.getBoundingClientRect()
    const startX = windowPosition?.x ?? frame?.left ?? 100
    const startY = windowPosition?.y ?? frame?.top ?? 40
    windowDragStart.current = { mouseX: e.clientX, mouseY: e.clientY, startX, startY }
    try { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId) } catch { /* ok */ }
  }

  function moveWindowDrag(e: PointerEvent<HTMLDivElement>) {
    if (!windowDragStart.current) return
    const dx = e.clientX - windowDragStart.current.mouseX
    const dy = e.clientY - windowDragStart.current.mouseY
    const newX = Math.max(10, Math.min(window.innerWidth - 300, windowDragStart.current.startX + dx))
    const newY = Math.max(0, Math.min(window.innerHeight - 100, windowDragStart.current.startY + dy))
    setWindowPosition({ x: newX, y: newY })
  }

  function endWindowDrag(e: PointerEvent<HTMLDivElement>) {
    if (windowDragStart.current) {
      try { (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId) } catch { /* ok */ }
      windowDragStart.current = null
    }
  }

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

    // Stage 5: Launch attempted (traveling across Windows desktop)
    setLaunchState('launching')
    setAvatarState('Working')
    setFacing('left')
    const targetCoord = DESKTOP_SHORTCUT_TARGETS[intent.appId] || { x: 30, y: 185 }
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
  }, [executionMode, updateProgressStage])

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
          // Web speech network error is expected in Electron because Google blocks Chromium apps.
          // Fallback to Windows Voice Typing (Win + H) notice and maintain listening state.
          setNotice('🎤 Windows Voice Typing active (Win + H). Speak into the prompt or type commands.')
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

  // ── Derived avatar values ───────────────────────────────────────────────────
  const activeTasks = tasks.filter((t) => t.status === 'Pending')
  const currentAvatarState = isSleeping ? 'Idle' : avatarState
  const animState = toAnimState(currentAvatarState, isSleeping, launchState, isVoiceRecording)
  const isMoving = launchState === 'launching' || launchState === 'running'

  const currentPos = floatingPosition || {
    x: typeof window !== 'undefined' ? Math.max(80, window.innerWidth - (isAssistantPanelOpen ? 460 : 200)) : 800,
    y: typeof window !== 'undefined' ? Math.max(80, window.innerHeight - 250) : 500,
  }

  const companionStyle: CSSProperties = {
    position: 'fixed',
    left: `${currentPos.x}px`,
    top: `${currentPos.y}px`,
    right: 'auto',
    bottom: 'auto',
    zIndex: 9999,
    transition: isDragging
      ? 'none'
      : 'left 2.8s cubic-bezier(0.35, 0, 0.25, 1), top 2.8s cubic-bezier(0.35, 0, 0.25, 1)',
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
  function stopTasks() {
    cancelActiveTask()
    setTasks((prev) => prev.map((t) => t.status === 'Pending' ? { ...t, status: 'Stopped' } : t))
    setIsPaused(false)
    setNotice(activeTasks.length ? 'Pending preview requests stopped.' : 'There are no pending requests to stop.')
  }

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
    if ((event.target as HTMLElement).closest('button, select, input, a, option')) return
    const rect = event.currentTarget.getBoundingClientRect()
    event.currentTarget.setPointerCapture(event.pointerId)
    dragOrigin.current = { x: event.clientX, y: event.clientY, left: rect.left, top: rect.top }
    setIsDragging(true)
  }

  function moveCompanion(event: PointerEvent<HTMLDivElement>) {
    const origin = dragOrigin.current
    if (!origin) return
    setFloatingPosition({
      x: Math.max(10, Math.min(window.innerWidth - 190, origin.left + event.clientX - origin.x)),
      y: Math.max(10, Math.min(window.innerHeight - 240, origin.top + event.clientY - origin.y)),
    })
  }

  function endCompanionDrag(event: PointerEvent<HTMLDivElement>) {
    setIsDragging(false)
    if (dragOrigin.current) {
      try { event.currentTarget.releasePointerCapture(event.pointerId) } catch { /* ok */ }
      dragOrigin.current = null
    }
  }

  function nudgeCompanion(event: KeyboardEvent<HTMLDivElement>) {
    const step = 20
    const defaultX = isAssistantPanelOpen ? Math.max(12, window.innerWidth - 530) : Math.max(12, window.innerWidth - 220)
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
    avatarDragStart.current = { x: event.screenX, y: event.screenY }
    try { event.currentTarget.setPointerCapture(event.pointerId) } catch { /* ok */ }
  }

  function moveAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    if (!avatarDragStart.current) return
    const dx = event.screenX - avatarDragStart.current.x
    const dy = event.screenY - avatarDragStart.current.y
    if (dx !== 0 || dy !== 0) {
      avatarDragStart.current = { x: event.screenX, y: event.screenY }
      if (window.companionAPI?.moveAvatar) window.companionAPI.moveAvatar(dx, dy)
    }
  }

  function endAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    if (avatarDragStart.current) {
      try { event.currentTarget.releasePointerCapture(event.pointerId) } catch { /* ok */ }
      avatarDragStart.current = null
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
        <div className="avatar-float-stage">
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

      {isWindowOpen && (
        <section
          className={`windows-app-frame ${isWindowMaximized ? 'window-maximized' : ''}`}
          aria-label="OmniCompanion application window"
          style={
            !isWindowMaximized && windowPosition
              ? { left: `${windowPosition.x}px`, top: `${windowPosition.y}px`, right: 'auto', bottom: 'auto', width: 'min(1120px, 86vw)', height: 'min(740px, 84vh)' }
              : undefined
          }
        >
          <header
            className="windows-titlebar"
            style={{ cursor: isWindowMaximized ? 'default' : 'move' }}
            onPointerDown={beginWindowDrag}
            onPointerMove={moveWindowDrag}
            onPointerUp={endWindowDrag}
            onPointerCancel={endWindowDrag}
            onDoubleClick={() => setIsWindowMaximized((v) => !v)}
          >
            <div className="windows-titlebar-brand"><span>✦</span><strong>OmniCompanion AI</strong></div>
            <div className="windows-titlebar-actions">
              <button aria-label="Minimize window" title="Minimize" onClick={() => setIsWindowOpen(false)}>－</button>
              <button aria-label={isWindowMaximized ? 'Restore window' : 'Maximize window'} title={isWindowMaximized ? 'Restore' : 'Maximize'} onClick={() => setIsWindowMaximized((v) => !v)}>{isWindowMaximized ? '❐' : '□'}</button>
              <button className="window-close" aria-label="Close window" title="Close" onClick={() => setIsWindowOpen(false)}>×</button>
            </div>
          </header>
          <div className="windows-app-content">
            <div className={`app-shell ${!isAssistantPanelOpen ? 'assistant-panel-closed' : ''}`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon" aria-hidden="true">✦</div>
          <div>
            <strong>JM VERTEX</strong>
            <span>DESKTOP COMPANION</span>
          </div>
        </div>

        <button className="new-chat" onClick={startNewConversation}>
          <span aria-hidden="true">＋</span> New conversation
        </button>

        <p className="side-label">WORKSPACE</p>
        <nav className="navigation" aria-label="Main navigation">
          {navigation.map(({ label, icon }) => (
            <button
              key={label}
              className={`nav-item ${activePage === label ? 'active' : ''}`}
              aria-current={activePage === label ? 'page' : undefined}
              onClick={() => setActivePage(label)}
            >
              <span className="nav-icon" aria-hidden="true">{icon}</span>
              {label}
              {label === 'Task History' && tasks.length > 0 && (
                <span className="nav-count">{tasks.length}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-status">
          <span className="status-light" />
          <div>
            <strong>LOCAL PREVIEW</strong>
            <span>No services connected</span>
          </div>
        </div>
        <div className="sidebar-footer">
          <span className="user-avatar">V</span>
          <div className="user-info">
            <strong>Local workspace</strong>
            <span>Personal desktop</span>
          </div>
          <span className="footer-menu" aria-hidden="true">···</span>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="breadcrumb-divider">/</span>
            <strong>{activePage}</strong>
          </div>
          <div className="topbar-meta">
            <button
              type="button"
              className="minimize-panel-btn"
              onClick={() => {
                if (window.companionAPI) {
                  window.companionAPI.wakeAvatar()
                  window.companionAPI.closeDashboard()
                } else {
                  setIsAssistantPanelOpen(false)
                }
              }}
              title="Minimize to floating avatar mode"
              aria-label="Minimize to floating avatar mode"
            >
              <span aria-hidden="true">⤢</span>
              <span>Float Avatar</span>
            </button>
            <span className="topbar-divider" />
            <button
              type="button"
              className={`mode-toggle-pill ${executionMode === 'real' ? 'mode-real' : 'mode-mock'}`}
              onClick={async () => {
                const next = executionMode === 'real' ? 'mock' : 'real'
                setExecutionMode(next)
                if (window.companionAPI?.setExecutionMode) {
                  await window.companionAPI.setExecutionMode(next)
                }
                setNotice(`Switched to ${next === 'real' ? 'Real Windows Execution' : 'Mock Simulation'} mode.`)
              }}
              title="Click to toggle between Real Windows Execution and Mock Simulation mode"
            >
              <span className="mode-dot" />
              {executionMode === 'real' ? 'REAL WINDOWS' : 'MOCK MODE'}
            </button>
            <span className="topbar-divider" />
            <span className="window-label">DESKTOP COMPANION</span>
          </div>
        </header>

        <div className="workspace-content">
          {activePage === 'Companion' && (
            <section className="companion-page" aria-label="Companion chat">
              <div className="page-heading">
                <div>
                  <span className="eyebrow">YOUR WORKSPACE</span>
                  <h1>Companion</h1>
                  <p>Plan your next step. Nothing runs without your review.</p>
                </div>
                <div className={`current-status status-${currentAvatarState.toLowerCase().replaceAll(' ', '-')}`}>
                  <span className="status-light" />
                  {isSleeping ? 'Sleeping' : isVoiceRecording ? 'Listening' : isPaused ? 'Paused' : currentAvatarState}
                </div>
              </div>

              <div className="chat-stage">
                <div className="chat-toolbar">
                  <div className="toolbar-title">
                    <span className="toolbar-sparkle">✦</span>
                    <div>
                      <strong>Assistant chat</strong>
                      <span>Voice & typed commands · try "Open Notepad", "Open Calculator", or "Open VS Code"</span>
                    </div>
                  </div>
                  <button className="subtle-button" onClick={startNewConversation}>
                    <span aria-hidden="true">＋</span> New chat
                  </button>
                </div>

                <div className="chat-scroll" aria-live="polite">
                  {messages.length === 0 ? (
                    <div className="welcome">
                      <div className={`welcome-orb state-${currentAvatarState.toLowerCase().replaceAll(' ', '-')}`}>
                        <span>✦</span>
                      </div>
                      <span className="eyebrow">OPEN APPS WITH VOICE OR TEXT</span>
                      <h2>What's on your mind?</h2>
                      <p>Speak with the microphone button or type: <em>"Open Notepad"</em>, <em>"Open Calculator"</em>, <em>"Open VS Code"</em></p>
                      <div className="suggestions">
                        {[
                          ['📝', 'Open Notepad', 'Launch Notepad text editor'],
                          ['🔢', 'Open Calculator', 'Launch Windows Calculator'],
                          ['📁', 'Open File Explorer', 'Browse files and folders'],
                          ['💻', 'Open VS Code', 'Launch Visual Studio Code'],
                        ].map(([icon, title, description]) => (
                          <button
                            className="suggestion-card"
                            key={title}
                            onClick={() => handleLaunchApp(title)}
                          >
                            <span className="suggestion-icon" aria-hidden="true">{icon}</span>
                            <span className="suggestion-copy">
                              <strong>{title}</strong>
                              <span>{description}</span>
                            </span>
                            <span className="card-arrow" aria-hidden="true">↗</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="conversation">
                      {messages.map((item) => (
                        <article className={`message message-${item.author.toLowerCase()}`} key={item.id}>
                          <span className={`message-avatar ${item.author === 'Companion' ? 'assistant-avatar' : ''}`}>
                            {item.author === 'You' ? 'V' : '✦'}
                          </span>
                          <div className="message-body">
                            <div className="message-meta">
                              <strong>{item.author}</strong>
                              <time>{item.time}</time>
                            </div>
                            <p>{item.text}</p>
                            {item.launchResult && <LaunchBanner result={item.launchResult} onCancel={cancelActiveTask} />}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>

                <div className="composer-area">
                  {/* Voice Error Notice */}
                  {voiceError && (
                    <div className="voice-error-banner" role="alert">
                      <span>⚠ {voiceError}</span>
                      <button aria-label="Dismiss error" onClick={() => setVoiceError(null)}>×</button>
                    </div>
                  )}

                  {/* Live Voice Recording & Transcript Preview Card */}
                  {(isVoiceRecording || voiceTranscript) && (
                    <div className="voice-preview-card" role="region" aria-label="Voice input preview">
                      <div className="voice-preview-header">
                        <div className="voice-indicator-wrap">
                          <span className={`voice-pulse-dot ${isVoiceRecording ? 'is-recording' : ''}`} />
                          <strong>{isVoiceRecording ? 'Listening… Speak your command' : 'Recognized Speech Transcript'}</strong>
                        </div>
                        {isVoiceRecording && (
                          <div className="voice-waveform" aria-hidden="true">
                            {[1, 2, 3, 4, 5, 6, 7].map((barIndex) => {
                              const dynamicHeight = Math.max(4, Math.min(24, Math.round((audioLevel / 100) * 22 * (0.6 + (barIndex % 3) * 0.25))))
                              return <span key={barIndex} className="waveform-bar" style={{ height: `${dynamicHeight}px` }} />
                            })}
                          </div>
                        )}
                      </div>

                      <div className="voice-transcript-text">
                        {voiceTranscript ? (
                          <span>"{voiceTranscript}"</span>
                        ) : (
                          <span className="voice-placeholder">Listening for command (e.g. "Open Notepad", "Open Calculator")…</span>
                        )}
                      </div>

                      <div className="voice-preview-actions">
                        {isVoiceRecording ? (
                          <button
                            type="button"
                            className="voice-action-btn stop-rec-btn"
                            onClick={handleToggleVoice}
                          >
                            ⏹ Stop Recording
                          </button>
                        ) : (
                          <>
                            <button
                              type="button"
                              className="voice-action-btn submit-voice-btn"
                              onClick={() => {
                                if (voiceTranscript.trim()) {
                                  handleLaunchApp(voiceTranscript.trim())
                                  setVoiceTranscript('')
                                }
                              }}
                              disabled={!voiceTranscript.trim()}
                            >
                              ↵ Submit Command
                            </button>
                            <button
                              type="button"
                              className="voice-action-btn retry-voice-btn"
                              onClick={handleToggleVoice}
                            >
                              ↻ Retry
                            </button>
                            <button
                              type="button"
                              className="voice-action-btn cancel-voice-btn"
                              onClick={() => {
                                setVoiceTranscript('')
                                setVoiceError(null)
                              }}
                            >
                              ✕ Dismiss
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  )}

                  {notice && (
                    <div className="notice" role="status">
                      <span aria-hidden="true">i</span>{notice}
                      <button aria-label="Dismiss notification" onClick={() => setNotice('')}>×</button>
                    </div>
                  )}

                  <form
                    className="composer"
                    onSubmit={(e) => { e.preventDefault(); sendMessage() }}
                  >
                    <label className="sr-only" htmlFor="message-input">Message your companion</label>
                    <textarea
                      id="message-input"
                      ref={messageInputRef}
                      value={message}
                      onChange={(e) => {
                        const val = e.target.value
                        setMessage(val)
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
                        }
                      }}
                      placeholder='Type or speak a command: "Open Notepad", "Open Calculator", "Open VS Code"…'
                      rows={2}
                      disabled={isSleeping || launchState === 'launching' || launchState === 'running'}
                    />
                    <div className="composer-footer">
                      <div className="composer-tools">
                        <button
                          className={`icon-button mic-button ${isVoiceRecording ? 'mic-active' : ''}`}
                          type="button"
                          aria-label={isVoiceRecording ? 'Stop voice recording' : 'Speak to Doraemon (Microphone)'}
                          title={isVoiceRecording ? 'Click to stop recording' : 'Speak with microphone'}
                          onClick={handleToggleVoice}
                        >
                          <span aria-hidden="true">{isVoiceRecording ? '⏹' : '🎤'}</span>
                        </button>
                        <span className="input-hint">Enter to send <kbd>↵</kbd></span>
                      </div>
                      <button
                        className="send-button"
                        type="submit"
                        disabled={!message.trim() || isSleeping || launchState === 'launching' || launchState === 'running'}
                      >
                        {launchState === 'launching' || launchState === 'running' ? 'Launching…' : 'Send'}{' '}
                        <span aria-hidden="true">↑</span>
                      </button>
                    </div>
                  </form>
                  <p className="privacy-note">
                    {window.companionAPI?.isElectron
                      ? 'Electron native mode — verified Windows process automation.'
                      : 'Web preview mode — microphone and desktop bridge ready.'}
                  </p>
                </div>
              </div>
            </section>
          )}

          {activePage === 'Task History' && (
            <section className="content-page">
              <span className="eyebrow">YOUR WORKSPACE</span>
              <h1>Task history</h1>
              <p className="page-description">All voice and typed requests including verified app launches this session.</p>
              {tasks.length === 0 ? (
                <div className="empty-state">
                  <span aria-hidden="true">◷</span>
                  <h2>No requests yet</h2>
                  <p>Requests and verified app launches will appear here.</p>
                  <button className="secondary-button" onClick={() => setActivePage('Companion')}>
                    Go to Companion
                  </button>
                </div>
              ) : (
                <div className="history-list">
                  {tasks.slice().reverse().map((task) => (
                    <article className="history-row" key={task.id}>
                      <span className="history-icon" aria-hidden="true">▤</span>
                      <div className="history-copy">
                        <strong>{task.title}</strong>
                        <span>
                          {task.launchResult
                            ? task.launchResult.realLaunch
                              ? `Real launch · ${task.launchResult.displayName} · ${task.launchResult.verified ? 'Verified in tasklist' : 'Window unverified'}`
                              : `Mock simulation mode · ${task.launchResult.displayName}`
                            : 'Conversation message'}
                        </span>
                        {task.launchResult && <LaunchBanner result={task.launchResult} />}
                      </div>
                      <span className={`task-status status-${task.status.toLowerCase()}`}>{task.status}</span>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {activePage === 'Settings' && (
            <section className="content-page">
              <span className="eyebrow">PREFERENCES & SAFETY</span>
              <h1>Settings</h1>
              <p className="page-description">Manage voice input, execution permissions, and companion controls.</p>
              <div className="settings-group">
                <div className="settings-group-heading">
                  <span className="settings-icon" aria-hidden="true">⌘</span>
                  <div><strong>Permissions</strong><span>Controls and access status for system services.</span></div>
                </div>
                <div className="permission-row">
                  <div><strong>Microphone Input</strong><span>Web Audio API and SpeechRecognition integration.</span></div>
                  <span className="permission-state" style={{ color: '#34D399' }}>CONNECTED</span>
                </div>
                <div className="permission-row">
                  <div><strong>Windows Automation</strong><span>Process verification via ShellExecute and tasklist.</span></div>
                  <span className="permission-state" style={{ color: '#34D399' }}>
                    {window.companionAPI?.isElectron ? 'LIVE' : 'BRIDGE READY'}
                  </span>
                </div>
              </div>
              <div className="settings-group">
                <div className="settings-group-heading">
                  <span className="settings-icon" aria-hidden="true">✦</span>
                  <div><strong>App Launcher</strong><span>Allowlisted applications: Notepad, Calculator, File Explorer, Chrome, VS Code, WhatsApp</span></div>
                </div>
                <div className="permission-row">
                  <div><strong>Launch mode</strong><span>{executionMode === 'real' ? 'Real Windows Execution' : 'Mock Simulation'}</span></div>
                  <span className="permission-state">{executionMode === 'real' ? 'REAL' : 'MOCK'}</span>
                </div>
                <div className="permission-row">
                  <div><strong>Arbitrary commands</strong><span>Never executed. Only allowlisted identifiers accepted.</span></div>
                  <span className="permission-state">BLOCKED</span>
                </div>
              </div>
            </section>
          )}
        </div>
      </main>

      <aside className="mission-panel" aria-label="Mission Control">
        <div className="mission-heading">
          <div>
            <span className="eyebrow">OVERVIEW</span>
            <h2>Mission Control</h2>
          </div>
          <span className="mission-mark" aria-hidden="true">⌘</span>
        </div>

        <section className="control-card" aria-label="Companion controls">
          <div className="control-card-heading">
            <span className="status-light" />
            <strong>{isSleeping ? 'Companion sleeping' : isVoiceRecording ? 'Listening to voice' : isPaused ? 'Companion paused' : 'Companion ready'}</strong>
            <span className="live-label">LOCAL</span>
          </div>
          <div className="control-actions">
            <button className="control-button pause-button" onClick={() => {
              setIsPaused((p) => !p)
              setNotice(isPaused ? 'Preview resumed.' : 'Preview paused.')
            }} disabled={isSleeping}>
              <span aria-hidden="true">{isPaused ? '▶' : 'Ⅱ'}</span>{isPaused ? 'Resume' : 'Pause'}
            </button>
            <button className="control-button stop-button" onClick={stopTasks} disabled={!liveProgress && activeTasks.length === 0}>
              <span aria-hidden="true">■</span>Stop
            </button>
          </div>
          <button className="sleep-button" onClick={() => {
            const next = !isSleeping
            setIsSleeping(next)
            setIsPaused(false)
            setNotice(next ? 'Companion is asleep.' : 'Companion woke up.')
            if (window.companionAPI) {
              if (next) { window.companionAPI.sleepAvatar() } else { window.companionAPI.wakeAvatar() }
              window.companionAPI.sendSyncState({ isSleeping: next })
            }
          }}>
            <span aria-hidden="true">{isSleeping ? '☼' : '☾'}</span>
            {isSleeping ? 'Wake companion' : 'Put companion to sleep'}
            <span className="sleep-arrow" aria-hidden="true">→</span>
          </button>
        </section>

        {/* Mission status & launch banner */}
        {currentLaunchResult && (
          <section className="mission-section" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 8, paddingBottom: 8 }}>
            <LaunchBanner result={currentLaunchResult} onCancel={cancelActiveTask} />
          </section>
        )}

        {/* ── Live Multi-Stage Task Timeline in Mission Control ── */}
        <section className="mission-section live-timeline-section">
          <div className="section-heading">
            <div>
              <h3>Task Timeline</h3>
              <p>{liveProgress?.rawCommand ? `"${liveProgress.rawCommand}"` : `${activeTasks.length} active · ${tasks.length} total`}</p>
            </div>
            {liveProgress && (
              <span style={{
                fontSize: 10,
                padding: '2px 6px',
                borderRadius: 4,
                fontWeight: 'bold',
                background: liveProgress.executionMode === 'real' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                color: liveProgress.executionMode === 'real' ? '#34D399' : '#FBBF24',
              }}>
                {liveProgress.executionMode === 'real' ? 'REAL' : 'MOCK'}
              </span>
            )}
          </div>

          {liveProgress ? (
            <>
              <div className="progress-block">
                <div className="progress-label">
                  <span>{liveProgress.currentStageId.toUpperCase().replaceAll('_', ' ')}</span>
                  <strong>{liveProgress.percent}%</strong>
                </div>
                <div className="progress-track" role="progressbar" aria-valuenow={liveProgress.percent} aria-valuemin={0} aria-valuemax={100}>
                  <span style={{ width: `${liveProgress.percent}%` }} />
                </div>
                <span className="progress-caption">
                  {liveProgress.currentStageId === 'launch_verified'
                    ? (liveProgress.isVerified ? '✔ Verified execution in Windows tasklist' : 'Attempted launch completed')
                    : liveProgress.currentStageId === 'failed'
                    ? `✖ Failed: ${liveProgress.error || 'Execution error'}`
                    : liveProgress.currentStageId === 'cancelled'
                    ? '⏹ Task cancelled by user'
                    : 'Windows automation in progress…'}
                </span>
              </div>

              {/* Active Cancel Task Button */}
              {liveProgress.currentStageId !== 'launch_verified' && liveProgress.currentStageId !== 'failed' && liveProgress.currentStageId !== 'cancelled' && (
                <button type="button" className="timeline-cancel-btn" onClick={cancelActiveTask}>
                  ⏹ Cancel Active Task
                </button>
              )}

              <ol className="live-stages-list">
                {liveProgress.stages.map((st) => {
                  const icon =
                    st.status === 'completed' ? '✔' :
                    st.status === 'in_progress' ? '⟳' :
                    st.status === 'failed' ? '✖' :
                    st.status === 'cancelled' ? '⏹' : '○'
                  return (
                    <li className={`timeline-item stage-${st.status}`} key={st.id}>
                      <span className="timeline-marker stage-marker">{icon}</span>
                      <div className="timeline-task">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <strong>{st.label}</strong>
                          {st.timestamp && <span style={{ fontSize: 10, opacity: 0.7 }}>{st.timestamp}</span>}
                        </div>
                        {st.detail && <span className="timeline-detail">{st.detail}</span>}
                      </div>
                    </li>
                  )
                })}
              </ol>
            </>
          ) : (
            <div className="timeline-empty">
              <span className="empty-timeline-icon" aria-hidden="true">⌁</span>
              <strong>All clear</strong>
              <p>Speak or type a command to view real-time stage progression.</p>
            </div>
          )}
        </section>

        <section className="permission-card">
          <div className="permission-card-heading">
            <span className="permission-icon" aria-hidden="true">◇</span>
            <div><strong>System Controls</strong><span>Hardware & automation status</span></div>
          </div>
          <div className="permission-line">
            <span>Microphone</span>
            <span className="permission-state" style={{ color: isVoiceRecording ? '#EF4444' : '#34D399' }}>
              {isVoiceRecording ? 'RECORDING' : 'READY'}
            </span>
          </div>
          <div className="permission-line">
            <span>Windows Automation</span>
            <span className="permission-state" style={{ color: '#34D399' }}>
              {window.companionAPI?.isElectron ? 'LIVE' : 'ACTIVE'}
            </span>
          </div>
          <button className="manage-permissions" onClick={() => setActivePage('Settings')}>
            Review permissions <span aria-hidden="true">→</span>
          </button>
        </section>

        <div className="mission-footer">JM VERTEX TECHNOLOGIES <span>·</span> COMPANION ENGINE</div>
      </aside>
            </div>
          </div>
        </section>
      )}

      {/* Floating Doraemon Desktop Companion (Always visible and moves across the desktop) */}
      <section
        className={`compact-floating-avatar state-${currentAvatarState.toLowerCase().replaceAll(' ', '-')} ${isSleeping ? 'is-sleeping' : ''} ${isMoving ? 'is-moving' : ''}`}
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
        <div className={`avatar-float-stage avatar-state-${animState}`}>
          {isSleeping && (
            <div className="avatar-zzz-cloud" aria-hidden="true">
              <span className="z1">z</span>
              <span className="z2">z</span>
              <span className="z3">Z</span>
            </div>
          )}

          <div className="avatar-image-wrapper">
            <AvatarCharacter state={animState} size={150} facing={facing} />
          </div>

          <div className="avatar-ground-shadow" aria-hidden="true" />
        </div>

        <div className="avatar-controls-dock" role="toolbar" aria-label="Avatar quick controls">
          <button
            type="button"
            className={`avatar-control-btn ${isWindowOpen ? 'active' : ''}`}
            onClick={(e) => {
              e.stopPropagation()
              setIsWindowOpen((p) => !p)
            }}
            title={isWindowOpen ? 'Minimize window' : 'Restore window'}
            aria-label={isWindowOpen ? 'Minimize window' : 'Restore window'}
          >
            <span className="control-icon" aria-hidden="true">✦</span>
            <span className="control-text">{isWindowOpen ? 'Hide' : 'Open'}</span>
          </button>

          <button
            type="button"
            className={`avatar-control-btn sleep-toggle ${isSleeping ? 'is-sleeping' : ''}`}
            onClick={(e) => {
              e.stopPropagation()
              setIsSleeping((p) => !p)
              setIsPaused(false)
              setNotice(isSleeping ? 'Companion woke up.' : 'Companion is now sleeping.')
            }}
            title={isSleeping ? 'Wake companion' : 'Put companion to sleep'}
            aria-label={isSleeping ? 'Wake companion' : 'Put companion to sleep'}
          >
            <span className="control-icon" aria-hidden="true">{isSleeping ? '☼' : '☾'}</span>
            <span className="control-text">{isSleeping ? 'Wake' : 'Sleep'}</span>
          </button>
        </div>

        <div className="avatar-drag-hint" aria-hidden="true">
          <span>⠿</span>
          <span>Drag to move</span>
        </div>
      </section>

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
