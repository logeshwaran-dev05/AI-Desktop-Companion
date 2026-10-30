import { useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent, PointerEvent } from 'react'
import './App.css'
import './avatarAnimations.css'
import AvatarCharacter from './AvatarCharacter'
import type { AvatarAnimState } from './AvatarCharacter'
import {
  resolveAppIntent,
  isLaunchIntent,
  type LaunchState,
  type LaunchResult,
} from './launchStateMachine'

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

type TaskStatus = 'Pending' | 'Stopped'

type Task = {
  id: number
  title: string
  status: TaskStatus
  /** Attached launch result, if this task was an app-launch request */
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

/** Map the high-level AvatarState to an animation state for the SVG/sprite */
function toAnimState(avatarState: AvatarState, isSleeping: boolean, launchState: LaunchState): AvatarAnimState {
  if (isSleeping) return 'idle'
  if (launchState === 'running' || launchState === 'launching') return 'running'
  if (launchState === 'resolving' || launchState === 'planning') return 'thinking'
  if (launchState === 'success')     return 'success'
  if (launchState === 'error' || launchState === 'failed' || launchState === 'not-allowed' || launchState === 'not-in-electron') return 'error'
  if (launchState === 'cancelled') return 'cancelled'
  switch (avatarState) {
    case 'Thinking':          return 'thinking'
    case 'Working':           return 'thinking'
    case 'Approval Required': return 'waiting'
    case 'Success':           return 'success'
    case 'Warning':           return 'waiting'
    case 'Error':             return 'error'
    default:                  return 'idle'
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
    `Resolving…`

  const body =
    stateKey === 'error' || stateKey === 'failed' ? result.errorMessage :
    stateKey === 'cancelled'       ? 'Doraemon stopped safely and returned home.' :
    stateKey === 'launching'       ? (result.targetInfo?.explanation || 'Traveling across visible Windows desktop to target...') :
    stateKey === 'not-in-electron' ? 'Run the app with npm run app to launch real Windows applications.' :
    stateKey === 'not-allowed'     ? `Supported apps: Notepad, Calculator, File Explorer, Chrome, VS Code.` :
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
  const [approval, setApproval]         = useState<'Awaiting review' | 'Approved in preview' | 'Declined in preview'>('Awaiting review')
  const [isAssistantPanelOpen, setIsAssistantPanelOpen] = useState(true)
  const [notice, setNotice]             = useState('')
  const [floatingPosition, setFloatingPosition] = useState<{ x: number; y: number } | null>(null)

  // ── Launch state ────────────────────────────────────────────────────────────
  const [launchState, setLaunchState]   = useState<LaunchState>('idle')
  const [currentLaunchResult, setCurrentLaunchResult] = useState<LaunchResult | null>(null)
  const [facing, setFacing]             = useState<'left' | 'right'>('right')
  const [executionMode, setExecutionMode] = useState<'real' | 'mock'>('real')

  const dragOrigin    = useRef<{ x: number; y: number; left: number; top: number } | null>(null)
  const avatarDragStart = useRef<{ x: number; y: number } | null>(null)

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

  const cancelMovement = useCallback(() => {
    if (window.companionAPI?.cancelMovement) {
      window.companionAPI.cancelMovement()
    }
    setLaunchState('cancelled')
    setAvatarState('Error')
    setNotice('Desktop movement cancelled.')
  }, [])

  // ── Derived values ───────────────────────────────────────────────────────────
  const activeTasks      = tasks.filter((t) => t.status === 'Pending')
  const currentAvatarState = isSleeping ? 'Idle' : avatarState
  const animState = toAnimState(currentAvatarState, isSleeping, launchState)

  const companionStyle: CSSProperties = floatingPosition
    ? { position: 'fixed', left: `${floatingPosition.x}px`, top: `${floatingPosition.y}px`, right: 'auto', bottom: 'auto' }
    : {
        position: 'fixed',
        bottom: '24px',
        right: isAssistantPanelOpen ? '324px' : '36px',
        left: 'auto',
        top: 'auto',
      }

  // ── App launch handler ───────────────────────────────────────────────────────
  const handleLaunchApp = useCallback(async (rawText: string) => {
    // Step 1: Resolve intent
    setLaunchState('resolving')
    setAvatarState('Thinking')

    const now = new Date()
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    const intent = resolveAppIntent(rawText)
    if (!intent) {
      const result: LaunchResult = {
        state: 'not-allowed',
        displayName: rawText,
        appId: '',
        realLaunch: false,
        errorMessage: `No recognized application found in: "${rawText}". Permitted: Notepad, Calculator, File Explorer, Chrome, or VS Code.`,
      }
      setLaunchState('not-allowed')
      setCurrentLaunchResult(result)
      setAvatarState('Error')
      setMessages((prev) => [
        ...prev,
        { id: Date.now(), author: 'You', text: rawText, time: timeStr },
        { id: Date.now() + 1, author: 'Companion', text: result.errorMessage ?? '', time: timeStr, launchResult: result },
      ])
      setTasks((prev) => [...prev, { id: Date.now() + 2, title: rawText, status: 'Stopped', launchResult: result }])
      setTimeout(() => { setLaunchState('idle'); setAvatarState('Idle') }, 4000)
      return
    }

    // Step 2: Planning & Target Discovery
    setLaunchState('planning')
    setAvatarState('Thinking')
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), author: 'You', text: rawText, time: timeStr },
    ])

    await new Promise((r) => setTimeout(r, 400))

    // Step 3: Desktop Movement & Launch
    setLaunchState('launching')
    setAvatarState('Working')

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
      // In browser preview mode, use the local dev server backend endpoint
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

    // Step 4: Handle completion / cancellation / failure
    if (taskResult.cancelled) {
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
          text: `Movement cancelled. Doraemon stopped safely.`,
          time: timeStr,
          launchResult: result,
        },
      ])
      setTimeout(() => { setLaunchState('idle'); setAvatarState('Idle') }, 3500)
      return
    }

    if (taskResult.success) {
      const isMock = taskResult.mode === 'mock' || taskResult.mockSimulated
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

      const destinationDesc = taskResult.targetInfo
        ? (taskResult.targetInfo.destinationType === 'desktop-shortcut' ? 'desktop shortcut' : 'launcher zone')
        : 'destination'

      const successText = isMock
        ? `[MOCK MODE] Simulated launch of ${taskResult.displayName}. Doraemon traveled across the desktop to the shortcut target.`
        : `${taskResult.displayName} opened! Doraemon traveled across the Windows desktop to the ${destinationDesc} and launched the application.`

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
      setTasks((prev) => [...prev, { id: Date.now() + 2, title: rawText, status: 'Pending', launchResult: result }])

      // Celebrate at destination, then safely return home
      setTimeout(() => {
        setLaunchState('idle')
        setAvatarState('Idle')
        if (window.companionAPI?.returnHome) {
          window.companionAPI.returnHome()
        }
      }, 5000)
    } else {
      const result: LaunchResult = {
        state: 'failed',
        displayName: taskResult.displayName,
        appId: intent.appId,
        realLaunch: taskResult.mode === 'real',
        errorMessage: taskResult.error ?? 'Unknown launch error.',
        targetInfo: taskResult.targetInfo,
        executionMode: taskResult.executionMode,
      }
      setLaunchState('failed')
      setCurrentLaunchResult(result)
      setAvatarState('Error')
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          author: 'Companion',
          text: `Failed to open ${taskResult.displayName}: ${taskResult.error ?? 'Unknown error.'}`,
          time: timeStr,
          launchResult: result,
        },
      ])
      setTasks((prev) => [...prev, { id: Date.now() + 2, title: rawText, status: 'Stopped', launchResult: result }])
      setTimeout(() => { setLaunchState('idle'); setAvatarState('Idle') }, 5000)
    }
  }, [executionMode])

  // ── Send message / dispatch to launch handler or normal flow ─────────────────
  function sendMessage() {
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
    setTasks((prev) => [...prev, { id: Date.now() + 2, title: text, status: 'Pending' }])
    setAvatarState('Idle')
    setNotice('Request added to the local preview.')
  }

  // ── Companion drag (browser mode) ─────────────────────────────────────────
  function stopTasks() {
    setTasks((prev) => prev.map((t) => t.status === 'Pending' ? { ...t, status: 'Stopped' } : t))
    setIsPaused(false)
    setNotice(activeTasks.length ? 'Pending preview requests stopped.' : 'There are no pending requests to stop.')
  }

  function startNewConversation() {
    setMessages([])
    setTasks([])
    setLaunchState('idle')
    setCurrentLaunchResult(null)
    setAvatarState('Idle')
    setNotice('Started a new local conversation.')
  }

  function beginCompanionDrag(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return
    if ((event.target as HTMLElement).closest('button, select, input, a, option')) return
    const rect = event.currentTarget.getBoundingClientRect()
    event.currentTarget.setPointerCapture(event.pointerId)
    dragOrigin.current = { x: event.clientX, y: event.clientY, left: rect.left, top: rect.top }
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
            onClick={() => {
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
            onClick={() => {
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

          <div className="avatar-state-select-wrapper" title="Avatar state preview">
            <select
              id="avatar-state-select"
              aria-label="Avatar state preview selector"
              value={avatarState}
              onChange={(e) => {
                const s = avatarStates.find((st) => st === e.target.value)
                if (s) {
                  setAvatarState(s)
                  if (window.companionAPI) window.companionAPI.sendSyncState({ avatarState: s })
                }
              }}
              disabled={isSleeping}
            >
              {avatarStates.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        <div className="avatar-drag-hint" aria-hidden="true">
          <span>⠿</span>
          <span>Drag to move</span>
        </div>
      </div>
    )
  }

  // ── Dashboard View ────────────────────────────────────────────────────────────
  return (
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
                  {isSleeping ? 'Sleeping' : isPaused ? 'Paused' : currentAvatarState}
                </div>
              </div>

              <div className="chat-stage">
                <div className="chat-toolbar">
                  <div className="toolbar-title">
                    <span className="toolbar-sparkle">✦</span>
                    <div>
                      <strong>Assistant chat</strong>
                      <span>Local preview · type "open notepad" to test real launch</span>
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
                      <span className="eyebrow">OPEN APPS WITH A SENTENCE</span>
                      <h2>What's on your mind?</h2>
                      <p>Try: <em>"Open Notepad"</em>, <em>"Launch Calculator"</em>, or <em>"Start File Explorer"</em></p>
                      <div className="suggestions">
                        {[
                          ['📝', 'Open Notepad', 'Launch Notepad text editor'],
                          ['🔢', 'Launch Calculator', 'Open the Windows Calculator'],
                          ['📁', 'Open File Explorer', 'Browse your files and folders'],
                        ].map(([icon, title, description]) => (
                          <button
                            className="suggestion-card"
                            key={title}
                            onClick={() => setMessage(title)}
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
                            {item.launchResult && <LaunchBanner result={item.launchResult} onCancel={cancelMovement} />}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>

                <div className="composer-area">
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
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
                      }}
                      placeholder='Type "open notepad" to launch a real Windows app…'
                      rows={2}
                      disabled={isSleeping || launchState === 'launching' || launchState === 'running'}
                    />
                    <div className="composer-footer">
                      <div className="composer-tools">
                        <button
                          className="icon-button mic-button"
                          type="button"
                          aria-label="Microphone unavailable in preview"
                          title="Voice input is not connected"
                          onClick={() => setNotice('Voice input is not connected in this UI preview.')}
                        >
                          <span aria-hidden="true">◉</span>
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
                      ? 'Electron mode — app launch commands run real Windows processes.'
                      : 'Browser preview — app launching requires npm run app (Electron).'}
                  </p>
                </div>
              </div>
            </section>
          )}

          {activePage === 'Task History' && (
            <section className="content-page">
              <span className="eyebrow">YOUR WORKSPACE</span>
              <h1>Task history</h1>
              <p className="page-description">All requests including real app launches this session.</p>
              {tasks.length === 0 ? (
                <div className="empty-state">
                  <span aria-hidden="true">◷</span>
                  <h2>No requests yet</h2>
                  <p>Requests and app launches will appear here.</p>
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
                              ? `Real launch · ${task.launchResult.displayName} · ${task.launchResult.state}`
                              : `Browser mode · cannot verify real launch`
                            : 'Local preview request · no action executed'}
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
              <p className="page-description">Manage preview controls and review connection status.</p>
              <div className="settings-group">
                <div className="settings-group-heading">
                  <span className="settings-icon" aria-hidden="true">⌘</span>
                  <div><strong>Permissions</strong><span>No operating-system permissions are requested by this preview.</span></div>
                </div>
                <div className="permission-row">
                  <div><strong>Accessibility control</strong><span>Windows automation is not connected.</span></div>
                  <span className="permission-state">NOT CONNECTED</span>
                </div>
                <div className="permission-row">
                  <div><strong>Screen and window access</strong><span>Screen capture is not connected.</span></div>
                  <span className="permission-state">NOT CONNECTED</span>
                </div>
              </div>
              <div className="settings-group">
                <div className="settings-group-heading">
                  <span className="settings-icon" aria-hidden="true">✦</span>
                  <div><strong>App Launcher</strong><span>Allowlisted apps: Notepad, Calculator, File Explorer, Chrome, VS Code</span></div>
                </div>
                <div className="permission-row">
                  <div><strong>Launch mode</strong><span>{window.companionAPI?.isElectron ? 'Electron IPC (real process)' : 'Browser preview (IPC unavailable)'}</span></div>
                  <span className="permission-state">{window.companionAPI?.isElectron ? 'LIVE' : 'OFFLINE'}</span>
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
            <strong>{isSleeping ? 'Companion sleeping' : isPaused ? 'Companion paused' : 'Companion ready'}</strong>
            <span className="live-label">LOCAL</span>
          </div>
          <div className="control-actions">
            <button className="control-button pause-button" onClick={() => {
              setIsPaused((p) => !p)
              setNotice(isPaused ? 'Preview resumed.' : 'Preview paused.')
            }} disabled={isSleeping}>
              <span aria-hidden="true">{isPaused ? '▶' : 'Ⅱ'}</span>{isPaused ? 'Resume' : 'Pause'}
            </button>
            <button className="control-button stop-button" onClick={stopTasks} disabled={activeTasks.length === 0}>
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

        {/* Live avatar display in mission panel */}
        <section className="mission-section" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 16, paddingBottom: 8 }}>
          <AvatarCharacter state={animState} size={110} facing={facing} />
          {currentLaunchResult && <LaunchBanner result={currentLaunchResult} onCancel={cancelMovement} />}
        </section>

        <section className="mission-section">
          <div className="section-heading">
            <div><h3>Task timeline</h3><p>{activeTasks.length} active · {tasks.length} total</p></div>
            <span className="section-icon" aria-hidden="true">◷</span>
          </div>
          <div className="progress-block">
            <div className="progress-label"><span>Session progress</span><strong>{tasks.length ? '0%' : '—'}</strong></div>
            <div className="progress-track" role="progressbar" aria-label="Task session progress" aria-valuenow={0} aria-valuemin={0} aria-valuemax={100}>
              <span />
            </div>
            <span className="progress-caption">{tasks.length ? 'Requests are queued for review' : 'No active requests'}</span>
          </div>

          {activeTasks.length === 0 ? (
            <div className="timeline-empty">
              <span className="empty-timeline-icon" aria-hidden="true">⌁</span>
              <strong>All clear</strong>
              <p>Your task timeline will appear here when you add a request.</p>
            </div>
          ) : (
            <ol className="timeline-list">
              {activeTasks.slice().reverse().map((task) => (
                <li className="timeline-item" key={task.id}>
                  <span className="timeline-marker" />
                  <div className="timeline-task">
                    <strong>{task.title}</strong>
                    <span className="timeline-detail">
                      {task.launchResult?.realLaunch ? 'Real launch attempt' : 'Waiting for review'}
                    </span>
                    <span className="task-status status-pending">Pending</span>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="approval-card">
          <div className="approval-heading">
            <span className="approval-icon" aria-hidden="true">!</span>
            <div><strong>Approval requests</strong><span>Human review required</span></div>
          </div>
          <p className="approval-copy">Sample approval control. No action will be executed.</p>
          <span className={`approval-status ${approval === 'Awaiting review' ? 'approval-pending' : 'approval-decided'}`}>
            <span />{approval}
          </span>
          <div className="approval-actions">
            <button onClick={() => setApproval('Approved in preview')}>Approve</button>
            <button onClick={() => setApproval('Declined in preview')}>Decline</button>
          </div>
        </section>

        <section className="permission-card">
          <div className="permission-card-heading">
            <span className="permission-icon" aria-hidden="true">◇</span>
            <div><strong>Permission controls</strong><span>All access is disconnected</span></div>
          </div>
          <div className="permission-line"><span>Windows automation</span><span className="permission-state">OFF</span></div>
          <div className="permission-line"><span>Microphone</span><span className="permission-state">OFF</span></div>
          <button className="manage-permissions" onClick={() => setActivePage('Settings')}>
            Review permissions <span aria-hidden="true">→</span>
          </button>
        </section>

        <div className="mission-footer">JM VERTEX TECHNOLOGIES <span>·</span> UI PREVIEW</div>
      </aside>

      {/* Compact Floating Avatar (browser mode only; Electron uses separate window) */}
      {!window.companionAPI?.isElectron && (
        <section
          className={`compact-floating-avatar state-${currentAvatarState.toLowerCase().replaceAll(' ', '-')} ${isSleeping ? 'is-sleeping' : ''}`}
          style={companionStyle}
          role="region"
          aria-label="Floating companion avatar"
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
              <AvatarCharacter state={animState} size={140} facing={facing} />
            </div>

            <div className="avatar-ground-shadow" aria-hidden="true" />
          </div>

          <div className="avatar-controls-dock" role="toolbar" aria-label="Avatar quick controls">
            <button
              type="button"
              className={`avatar-control-btn ${isAssistantPanelOpen ? 'active' : ''}`}
              onClick={(e) => {
                e.stopPropagation()
                setIsAssistantPanelOpen((p) => !p)
                if (!isAssistantPanelOpen) setActivePage('Companion')
              }}
              title={isAssistantPanelOpen ? 'Minimize assistant panel' : 'Open assistant panel'}
              aria-label={isAssistantPanelOpen ? 'Minimize assistant panel' : 'Open assistant panel'}
            >
              <span className="control-icon" aria-hidden="true">✦</span>
              <span className="control-text">{isAssistantPanelOpen ? 'Panel' : 'Open'}</span>
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

            <div className="avatar-state-select-wrapper" title="Avatar state preview">
              <select
                id="avatar-state-select"
                aria-label="Avatar state preview selector"
                value={avatarState}
                onChange={(e) => {
                  const s = avatarStates.find((st) => st === e.target.value)
                  if (s) setAvatarState(s)
                }}
                disabled={isSleeping}
              >
                {avatarStates.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          <div className="avatar-drag-hint" aria-hidden="true">
            <span>⠿</span>
            <span>Drag to move</span>
          </div>
        </section>
      )}
    </div>
  )
}

export default App
