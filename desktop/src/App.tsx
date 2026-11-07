import { useEffect, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent, PointerEvent } from 'react'
import './App.css'

type Page = 'Companion' | 'Task History' | 'Settings'
type AvatarState =
  | 'Idle'
  | 'Listening'
  | 'Thinking'
  | 'Working'
  | 'Approval Required'
  | 'Success'
  | 'Warning'
  | 'Error'
type TaskStatus = 'Pending' | 'Running' | 'Completed' | 'Failed' | 'Stopped'
type Task = {
  id: number
  title: string
  status: TaskStatus
}
type Message = {
  id: number
  author: 'You' | 'Companion'
  text: string
  time: string
}

const avatarStates: AvatarState[] = [
  'Idle',
  'Listening',
  'Thinking',
  'Working',
  'Approval Required',
  'Success',
  'Warning',
  'Error',
]

const navigation: { label: Page; icon: string }[] = [
  { label: 'Companion', icon: '◈' },
  { label: 'Task History', icon: '◷' },
  { label: 'Settings', icon: '⚙' },
]

function App() {
  const [viewMode] = useState<'avatar' | 'dashboard'>(() => {
    if (typeof window === 'undefined') return 'dashboard'
    const params = new URLSearchParams(window.location.search)
    if (params.get('view') === 'avatar' || window.location.hash === '#avatar') {
      return 'avatar'
    }
    return 'dashboard'
  })

  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [activePage, setActivePage] = useState<Page>('Companion')
  const [avatarState, setAvatarState] = useState<AvatarState>('Idle')
  const [isPaused, setIsPaused] = useState(false)
  const [isSleeping, setIsSleeping] = useState(false)
  const [approval, setApproval] = useState<'Awaiting review' | 'Approved in preview' | 'Declined in preview'>('Awaiting review')
  const [isAssistantPanelOpen, setIsAssistantPanelOpen] = useState(true)
  const [avatarImageSrc, setAvatarImageSrc] = useState('/companion.webp')
  const [notice, setNotice] = useState('')
  const [floatingPosition, setFloatingPosition] = useState<{ x: number; y: number } | null>(null)
  const dragOrigin = useRef<{ x: number; y: number; left: number; top: number } | null>(null)
  const avatarDragStart = useRef<{ x: number; y: number } | null>(null)

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
      })
      return cleanup
    }
  }, [viewMode])

  const activeTasks = tasks.filter((task) => task.status === 'Pending' || task.status === 'Running')
  const currentAvatarState = isSleeping ? 'Idle' : avatarState
  const companionStyle: CSSProperties = floatingPosition
    ? { position: 'fixed', left: `${floatingPosition.x}px`, top: `${floatingPosition.y}px`, right: 'auto', bottom: 'auto' }
    : {
        position: 'fixed',
        bottom: '24px',
        right: isAssistantPanelOpen ? '324px' : '36px',
        left: 'auto',
        top: 'auto',
      }

  async function sendMessage() {
    const text = message.trim()
    if (!text || isSleeping) return

    const now = new Date()
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    const taskId = Date.now()
    const compMsgId = taskId + 1

    setMessages((previous) => [
      ...previous,
      { id: taskId, author: 'You', text, time: timeStr },
    ])
    setTasks((previous) => [...previous, { id: taskId, title: text, status: 'Running' }])
    setMessage('')
    setAvatarState('Thinking')
    setNotice('Companion is processing your request...')

    try {
      const response = await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: text }),
      })

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`)
      }

      const data = await response.json()
      const replyText = data.reply || 'Action completed.'
      const newAvatarState: AvatarState = data.avatar_state && avatarStates.includes(data.avatar_state as AvatarState)
        ? (data.avatar_state as AvatarState)
        : (data.status === 'success' ? 'Success' : 'Idle')

      setMessages((previous) => [
        ...previous,
        { id: compMsgId, author: 'Companion', text: replyText, time: timeStr },
      ])

      setTasks((previous) =>
        previous.map((t) =>
          t.id === taskId
            ? { ...t, status: data.status === 'success' ? 'Completed' : (data.status === 'failed' ? 'Failed' : 'Completed') }
            : t
        )
      )

      setAvatarState(newAvatarState)
      setNotice(data.status === 'success' ? `Task completed: ${replyText}` : replyText)

      if (newAvatarState === 'Success') {
        setTimeout(() => setAvatarState('Idle'), 4000)
      }
    } catch {
      setMessages((previous) => [
        ...previous,
        {
          id: compMsgId,
          author: 'Companion',
          text: 'Request saved in this local preview. (Companion API offline)',
          time: timeStr,
        },
      ])
      setTasks((previous) =>
        previous.map((t) => (t.id === taskId ? { ...t, status: 'Pending' } : t))
      )
      setAvatarState('Idle')
      setNotice('Request added to local preview.')
    }
  }

  function stopTasks() {
    setTasks((previous) =>
      previous.map((task) => (task.status === 'Pending' || task.status === 'Running' ? { ...task, status: 'Stopped' } : task)),
    )
    setIsPaused(false)
    setNotice(activeTasks.length ? 'Pending preview requests stopped.' : 'There are no pending requests to stop.')
  }

  function startNewConversation() {
    setMessages([])
    setTasks([])
    setNotice('Started a new local conversation.')
  }

  function beginCompanionDrag(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return
    if ((event.target as HTMLElement).closest('button, select, input, a, option')) {
      return
    }
    const rect = event.currentTarget.getBoundingClientRect()
    event.currentTarget.setPointerCapture(event.pointerId)
    dragOrigin.current = { x: event.clientX, y: event.clientY, left: rect.left, top: rect.top }
  }

  function moveCompanion(event: PointerEvent<HTMLDivElement>) {
    const origin = dragOrigin.current
    if (!origin) return
    const avatarWidth = 190
    const avatarHeight = 240
    setFloatingPosition({
      x: Math.max(10, Math.min(window.innerWidth - avatarWidth, origin.left + event.clientX - origin.x)),
      y: Math.max(10, Math.min(window.innerHeight - avatarHeight, origin.top + event.clientY - origin.y)),
    })
  }

  function endCompanionDrag(event: PointerEvent<HTMLDivElement>) {
    if (dragOrigin.current) {
      try {
        event.currentTarget.releasePointerCapture(event.pointerId)
      } catch {
        // pointer capture release
      }
      dragOrigin.current = null
    }
  }

  function nudgeCompanion(event: KeyboardEvent<HTMLDivElement>) {
    const step = 20
    const defaultX = isAssistantPanelOpen ? Math.max(12, window.innerWidth - 530) : Math.max(12, window.innerWidth - 220)
    const defaultY = Math.max(12, window.innerHeight - 300)
    const left = floatingPosition?.x ?? defaultX
    const top = floatingPosition?.y ?? defaultY
    const moves: Record<string, { x: number; y: number }> = {
      ArrowLeft: { x: -step, y: 0 },
      ArrowRight: { x: step, y: 0 },
      ArrowUp: { x: 0, y: -step },
      ArrowDown: { x: 0, y: step },
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
    if ((event.target as HTMLElement).closest('button, select, input, a, option, .no-drag-region')) {
      return
    }
    avatarDragStart.current = { x: event.screenX, y: event.screenY }
    try {
      event.currentTarget.setPointerCapture(event.pointerId)
    } catch {
      // ignore
    }
  }

  function moveAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    if (!avatarDragStart.current) return
    const dx = event.screenX - avatarDragStart.current.x
    const dy = event.screenY - avatarDragStart.current.y
    if (dx !== 0 || dy !== 0) {
      avatarDragStart.current = { x: event.screenX, y: event.screenY }
      if (window.companionAPI?.moveAvatar) {
        window.companionAPI.moveAvatar(dx, dy)
      }
    }
  }

  function endAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    if (avatarDragStart.current) {
      try {
        event.currentTarget.releasePointerCapture(event.pointerId)
      } catch {
        // ignore
      }
      avatarDragStart.current = null
    }
  }

  // Standalone Frameless Transparent Avatar Window Mode in Electron
  if (viewMode === 'avatar') {
    return (
      <div
        className={`standalone-avatar-window state-${currentAvatarState.toLowerCase().replaceAll(' ', '-')} ${
          isSleeping ? 'is-sleeping' : ''
        }`}
        role="region"
        aria-label="Floating Companion Avatar"
        onPointerDown={beginAvatarDrag}
        onPointerMove={moveAvatarDrag}
        onPointerUp={endAvatarDrag}
        onPointerCancel={endAvatarDrag}
      >
        <div className="avatar-float-stage">
          {/* Animated Zzz particles when sleeping */}
          {isSleeping && (
            <div className="avatar-zzz-cloud" aria-hidden="true">
              <span className="z1">z</span>
              <span className="z2">z</span>
              <span className="z3">Z</span>
            </div>
          )}

          {/* Draggable avatar image with transparent background */}
          <div className="avatar-image-wrapper">
            <img
              src={avatarImageSrc}
              alt="Desktop Companion Avatar"
              className="avatar-character-img"
              draggable={false}
              onError={() => {
                if (avatarImageSrc === '/companion.webp') {
                  setAvatarImageSrc('/companion.webp.png')
                }
              }}
            />
          </div>

          {/* Ground shadow beneath avatar */}
          <div className="avatar-ground-shadow" aria-hidden="true" />
        </div>

        {/* Small controls toolbar dock with no-drag-region */}
        <div className="avatar-controls-dock no-drag-region" role="toolbar" aria-label="Avatar quick controls">
          <button
            type="button"
            className="avatar-control-btn active"
            onClick={() => {
              if (window.companionAPI) {
                window.companionAPI.openDashboard()
              } else {
                window.location.search = '?view=dashboard'
              }
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
                setNotice('Companion woke up.')
                if (window.companionAPI) {
                  window.companionAPI.sendSyncState({ isSleeping: false })
                }
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
                const selectedState = avatarStates.find((state) => state === e.target.value)
                if (selectedState) {
                  setAvatarState(selectedState)
                  if (window.companionAPI) {
                    window.companionAPI.sendSyncState({ avatarState: selectedState })
                  }
                }
              }}
              disabled={isSleeping}
            >
              {avatarStates.map((state) => (
                <option key={state} value={state}>
                  {state}
                </option>
              ))}
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
            <span className="preview-chip"><span /> UI PREVIEW</span>
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
                      <span>Local preview · no AI connected</span>
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
                      <span className="eyebrow">A CALMER WAY TO GET THINGS DONE</span>
                      <h2>What’s on your mind?</h2>
                      <p>Describe a task to add it to your local preview timeline.</p>
                      <div className="suggestions">
                        {[
                          ['⌘', 'Organize my work', 'Turn a busy day into a clear plan'],
                          ['▤', 'Summarize information', 'Collect the important points'],
                          ['↗', 'Plan a workflow', 'Outline a process for review'],
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
                    onSubmit={(event) => {
                      event.preventDefault()
                      sendMessage()
                    }}
                  >
                    <label className="sr-only" htmlFor="message-input">Message your companion</label>
                    <textarea
                      id="message-input"
                      value={message}
                      onChange={(event) => setMessage(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' && !event.shiftKey) {
                          event.preventDefault()
                          sendMessage()
                        }
                      }}
                      placeholder="Describe a task or ask for help planning..."
                      rows={2}
                      disabled={isSleeping}
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
                      <button className="send-button" type="submit" disabled={!message.trim() || isSleeping}>
                        Add request <span aria-hidden="true">↑</span>
                      </button>
                    </div>
                  </form>
                  <p className="privacy-note">Connected to Windows Automation Companion engine.</p>
                </div>
              </div>
            </section>
          )}

          {activePage === 'Task History' && (
            <section className="content-page">
              <span className="eyebrow">YOUR WORKSPACE</span>
              <h1>Task history</h1>
              <p className="page-description">Requests saved in this session’s local preview.</p>
              {tasks.length === 0 ? (
                <div className="empty-state">
                  <span aria-hidden="true">◷</span>
                  <h2>No requests yet</h2>
                  <p>Requests you add in Companion will be listed here.</p>
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
                        <span>Local preview request · no action executed</span>
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
                  <div><strong>Assistant services</strong><span>All integrations are placeholders in this UI preview.</span></div>
                </div>
                <div className="permission-row">
                  <div><strong>AI planner</strong><span>No AI provider or backend is configured.</span></div>
                  <span className="permission-state">OFFLINE</span>
                </div>
                <div className="permission-row">
                  <div><strong>Microphone</strong><span>Voice input is not active.</span></div>
                  <span className="permission-state">OFFLINE</span>
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
              setIsPaused((previous) => !previous)
              setNotice(isPaused ? 'Preview resumed.' : 'Preview paused.')
            }} disabled={isSleeping}>
              <span aria-hidden="true">{isPaused ? '▶' : 'Ⅱ'}</span>{isPaused ? 'Resume' : 'Pause'}
            </button>
            <button className="control-button stop-button" onClick={stopTasks} disabled={activeTasks.length === 0}>
              <span aria-hidden="true">■</span>Stop
            </button>
          </div>
          <button className="sleep-button" onClick={() => {
            const nextSleeping = !isSleeping
            setIsSleeping(nextSleeping)
            setIsPaused(false)
            setNotice(nextSleeping ? 'Companion is asleep in the local preview.' : 'Companion woke in the local preview.')
            if (window.companionAPI) {
              if (nextSleeping) {
                window.companionAPI.sleepAvatar()
              } else {
                window.companionAPI.wakeAvatar()
              }
              window.companionAPI.sendSyncState({ isSleeping: nextSleeping })
            }
          }}>
            <span aria-hidden="true">{isSleeping ? '☼' : '☾'}</span>
            {isSleeping ? 'Wake companion' : 'Put companion to sleep'}
            <span className="sleep-arrow" aria-hidden="true">→</span>
          </button>
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
                    <span className="timeline-detail">Waiting for review</span>
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

      {/* Compact Floating Avatar UI (rendered for browser preview; in Electron the companion floats in its own desktop window) */}
      {!window.companionAPI?.isElectron && (
        <section
          className={`compact-floating-avatar state-${currentAvatarState.toLowerCase().replaceAll(' ', '-')} ${
            isSleeping ? 'is-sleeping' : ''
          }`}
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
          <div className="avatar-float-stage">
            {/* Animated Zzz particles when sleeping */}
            {isSleeping && (
              <div className="avatar-zzz-cloud" aria-hidden="true">
                <span className="z1">z</span>
                <span className="z2">z</span>
                <span className="z3">Z</span>
              </div>
            )}

            {/* Draggable avatar image with transparent background */}
            <div className="avatar-image-wrapper">
              <img
                src={avatarImageSrc}
                alt="Desktop Companion Avatar"
                className="avatar-character-img"
                draggable={false}
                onError={() => {
                  if (avatarImageSrc === '/companion.webp') {
                    setAvatarImageSrc('/companion.webp.png')
                  }
                }}
              />
            </div>

            {/* Ground shadow beneath avatar */}
            <div className="avatar-ground-shadow" aria-hidden="true" />
          </div>

          {/* Small controls toolbar dock */}
          <div className="avatar-controls-dock" role="toolbar" aria-label="Avatar quick controls">
            <button
              type="button"
              className={`avatar-control-btn ${isAssistantPanelOpen ? 'active' : ''}`}
              onClick={(e) => {
                e.stopPropagation()
                setIsAssistantPanelOpen((prev) => !prev)
                if (!isAssistantPanelOpen) {
                  setActivePage('Companion')
                }
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
                setIsSleeping((prev) => !prev)
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
                  const selectedState = avatarStates.find((state) => state === e.target.value)
                  if (selectedState) setAvatarState(selectedState)
                }}
                disabled={isSleeping}
              >
                {avatarStates.map((state) => (
                  <option key={state} value={state}>
                    {state}
                  </option>
                ))}
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
