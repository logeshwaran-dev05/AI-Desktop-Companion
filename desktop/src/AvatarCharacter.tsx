import { useState, useEffect } from 'react'
import type { CSSProperties } from 'react'

export type AvatarAnimState =
  | 'idle'
  | 'walking'
  | 'listening'
  | 'thinking'
  | 'waiting'
  | 'running'
  | 'success'
  | 'error'
  | 'cancelled'

interface AvatarCharacterProps {
  state: AvatarAnimState
  /** Width of the character in pixels. Height is calculated proportionally. */
  size?: number
  className?: string
  style?: CSSProperties
  /** Horizontal direction Doraemon is facing or walking */
  facing?: 'left' | 'right'
}

/** Pre-extracted walking frames (facing right natively, mirrored left during travel) */
const WALK_FRAMES = [
  '/doraemon/walk/walk_01.png?v=stride2',
  '/doraemon/walk/walk_02.png?v=stride2',
  '/doraemon/walk/walk_03.png?v=stride2',
  '/doraemon/walk/walk_04.png?v=stride2',
  '/doraemon/walk/walk_05.png?v=stride2',
  '/doraemon/walk/walk_06.png?v=stride2',
  '/doraemon/walk/walk_07.png?v=stride2',
  '/doraemon/walk/walk_08.png?v=stride2',
]

/**
 * Doraemon — Original Companion Character
 * ========================================
 * Renders the authentic Doraemon character with responsive state-driven
 * animations (animated walk cycle extracted directly from reference video,
 * floating Take-copter, sprint runs, celebration jumps, thought bubbles,
 * listening soundwaves, and sparkles).
 */
export default function AvatarCharacter({
  state,
  size = 160,
  className,
  style,
  facing = 'right',
}: AvatarCharacterProps) {
  const [imgSrc, setImgSrc] = useState('/companion.webp')
  const [walkFrameIdx, setWalkFrameIdx] = useState(0)

  const isWalking = state === 'walking' || state === 'running'
  const isListening = state === 'listening'
  const isRunning = state === 'running'
  const isSuccess = state === 'success'
  const isThinking = state === 'thinking'
  const isWaiting = state === 'waiting'
  const isError = state === 'error'
  const isCancelled = state === 'cancelled'

  // Preload all walking frames in memory so walking is instantaneous with zero stutter
  useEffect(() => {
    WALK_FRAMES.forEach((src) => {
      const img = new Image()
      img.src = src
    })
  }, [])

  // Step through the 8 walking frames at natural anime pace (~110ms per frame)
  useEffect(() => {
    if (!isWalking) return

    const timer = setInterval(() => {
      setWalkFrameIdx((prev) => (prev + 1) % WALK_FRAMES.length)
    }, 110)

    return () => {
      clearInterval(timer)
      setWalkFrameIdx(0)
    }
  }, [isWalking])

  const wrapperClass = [
    'avatar-char-wrap',
    'avatar-doraemon-wrap',
    `avatar-state-${state}`,
    className ?? '',
  ].join(' ')

  const currentDisplaySrc = isWalking ? WALK_FRAMES[walkFrameIdx] : imgSrc

  return (
    <div
      className={wrapperClass}
      style={{
        position: 'relative',
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        userSelect: 'none',
        ...style,
      }}
      aria-label={`Doraemon companion, state: ${state}`}
      role="img"
    >
      {/* ── Dynamic State Badges / Visual Effects ────────────────────────── */}

      {/* Listening state: Sound wave badge */}
      {isListening && (
        <div
          className="doraemon-fx-listening"
          style={{
            position: 'absolute',
            top: -14,
            right: 4,
            display: 'flex',
            alignItems: 'center',
            gap: 3,
            background: 'rgba(56, 189, 248, 0.22)',
            border: '1px solid rgba(56, 189, 248, 0.65)',
            borderRadius: 14,
            padding: '2px 8px',
            boxShadow: '0 0 14px rgba(56, 189, 248, 0.45)',
            pointerEvents: 'none',
            zIndex: 10,
          }}
          aria-hidden="true"
        >
          <span style={{ fontSize: 13, marginRight: 2 }}>🎙️</span>
          <span className="listening-bar bar-1" />
          <span className="listening-bar bar-2" />
          <span className="listening-bar bar-3" />
        </div>
      )}

      {/* Thinking state: Thought bubbles */}
      {isThinking && (
        <div
          className="doraemon-fx-thinking"
          style={{
            position: 'absolute',
            top: -12,
            right: 8,
            display: 'flex',
            gap: 4,
            pointerEvents: 'none',
            zIndex: 10,
          }}
          aria-hidden="true"
        >
          <span style={{ fontSize: 13, filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.25))' }}>💭</span>
        </div>
      )}

      {/* Success state: Sparkles and celebration stars */}
      {isSuccess && (
        <div
          className="doraemon-fx-success"
          style={{
            position: 'absolute',
            inset: -12,
            pointerEvents: 'none',
            zIndex: 10,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
          }}
          aria-hidden="true"
        >
          <span style={{ fontSize: 20, transform: 'rotate(-15deg)', filter: 'drop-shadow(0 2px 6px #F59E0B)' }}>✨</span>
          <span style={{ fontSize: 22, transform: 'rotate(20deg)', filter: 'drop-shadow(0 2px 6px #FBBF24)' }}>⭐</span>
        </div>
      )}

      {/* Running state: Wind / speed dash streaks (trail behind movement) */}
      {isRunning && (
        <div
          className="doraemon-fx-running"
          style={{
            position: 'absolute',
            bottom: 12,
            ...(facing === 'left'
              ? { right: -18, transform: 'scaleX(-1)' }
              : { left: -18, transform: 'none' }),
            pointerEvents: 'none',
            zIndex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 3,
            opacity: 0.85,
          }}
          aria-hidden="true"
        >
          <div style={{ width: 28, height: 3, background: '#38BDF8', borderRadius: 2 }} />
          <div style={{ width: 18, height: 3, background: '#60A5FA', borderRadius: 2, marginLeft: 6 }} />
          <div style={{ width: 24, height: 3, background: '#93C5FD', borderRadius: 2 }} />
        </div>
      )}

      {/* Waiting / Approval state: Attention badge */}
      {isWaiting && (
        <div
          className="doraemon-fx-waiting"
          style={{
            position: 'absolute',
            top: -4,
            right: 14,
            background: '#F59E0B',
            color: '#FFFFFF',
            borderRadius: '50%',
            width: 22,
            height: 22,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 13,
            fontWeight: 'bold',
            boxShadow: '0 2px 6px rgba(245, 158, 11, 0.45)',
            zIndex: 10,
          }}
          aria-hidden="true"
        >
          !
        </div>
      )}

      {/* Error / Cancelled state: Sweat / alert mark */}
      {(isError || isCancelled) && (
        <div
          className="doraemon-fx-error"
          style={{
            position: 'absolute',
            top: 2,
            right: 16,
            fontSize: 16,
            filter: 'drop-shadow(0 2px 4px rgba(239, 68, 68, 0.5))',
            pointerEvents: 'none',
            zIndex: 10,
          }}
          aria-hidden="true"
        >
          💧
        </div>
      )}

      {/* ── Doraemon Character Display (Walk frames or Idle Companion) ─── */}
      <img
        src={currentDisplaySrc}
        alt={`Doraemon companion — ${state}`}
        width={size}
        draggable={false}
        onError={() => {
          if (imgSrc === '/companion.webp') {
            setImgSrc('/companion.webp.png')
          }
        }}
        className={`avatar-character-img doraemon-character-img ${isWalking ? 'doraemon-walking-img' : ''} ${isRunning ? 'doraemon-running-tilt' : ''} ${facing === 'left' ? 'doraemon-facing-left' : 'doraemon-facing-right'}`}
        style={{
          display: 'block',
          width: size,
          height: 'auto',
          objectFit: 'contain',
          pointerEvents: 'none',
          userSelect: 'none',
          filter: isCancelled
            ? 'grayscale(0.4) brightness(0.85) drop-shadow(0 8px 16px rgba(0,0,0,0.35))'
            : isError
            ? 'drop-shadow(0 0 16px rgba(239, 68, 68, 0.55)) drop-shadow(0 12px 20px rgba(0,0,0,0.35))'
            : isSuccess
            ? 'drop-shadow(0 0 18px rgba(52, 211, 153, 0.6)) drop-shadow(0 12px 20px rgba(0,0,0,0.35))'
            : isWalking
            ? 'drop-shadow(0 0 16px rgba(56, 189, 248, 0.55)) drop-shadow(0 10px 18px rgba(0,0,0,0.35))'
            : isRunning
            ? 'drop-shadow(0 0 18px rgba(56, 189, 248, 0.6)) drop-shadow(0 12px 20px rgba(0,0,0,0.35))'
            : isListening
            ? 'drop-shadow(0 0 20px rgba(56, 189, 248, 0.75)) drop-shadow(0 12px 20px rgba(0,0,0,0.35))'
            : isThinking
            ? 'drop-shadow(0 0 16px rgba(168, 85, 247, 0.5)) drop-shadow(0 12px 20px rgba(0,0,0,0.35))'
            : 'drop-shadow(0 14px 22px rgba(0, 0, 0, 0.4)) drop-shadow(0 0 20px rgba(56, 189, 248, 0.25))',
          transition: 'filter 0.3s ease, transform 0.25s ease',
        }}
      />
    </div>
  )
}
