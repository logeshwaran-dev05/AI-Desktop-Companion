import { useState, useEffect } from 'react'
import type { CSSProperties } from 'react'

export type AvatarAnimState =
  | 'idle'
  | 'walking'
  | 'listening'
  | 'thinking'
  | 'waiting'
  | 'running'
  | 'greeting'
  | 'success'
  | 'error'
  | 'cancelled'

interface AvatarCharacterProps {
  state: AvatarAnimState
  /** Width of the character in pixels. Height is calculated proportionally. */
  size?: number
  className?: string
  style?: CSSProperties
  /** Horizontal direction Doraemon is facing or walking ('left' | 'right') */
  facing?: 'left' | 'right'
}

/** Pre-extracted walking frames for authentic animated walk cycle */
const WALK_FRAMES = [
  '/doraemon/walk/walk_01.png',
  '/doraemon/walk/walk_02.png',
  '/doraemon/walk/walk_03.png',
  '/doraemon/walk/walk_04.png',
  '/doraemon/walk/walk_05.png',
  '/doraemon/walk/walk_06.png',
  '/doraemon/walk/walk_07.png',
  '/doraemon/walk/walk_08.png',
]

/**
 * Doraemon — Original Authentic Companion Character
 * ==================================================
 * Implements:
 * 1. Genuine multi-frame walking cycle (alternating feet & swinging arms from WALK_FRAMES)
 *    during real desktop movement so Doraemon physically walks instead of shaking.
 * 2. Direction-aware turning (facing left/right) during travel.
 * 3. Authentic idle pose from /companion.webp with gentle breathing and eye-blink interval.
 * 4. Reactive visual effects: listening soundwaves, thought bubbles, celebration stars,
 *    and speed streaks.
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

  // Preload all walk frames in memory so walking is instantaneous with zero stutter
  useEffect(() => {
    WALK_FRAMES.forEach((src) => {
      const img = new Image()
      img.src = src
    })
  }, [])

  // Step through the 8 walking frames at natural anime pace (~105ms per frame, 75ms for running)
  useEffect(() => {
    if (!isWalking) {
      setWalkFrameIdx(0)
      return
    }

    const intervalMs = isRunning ? 75 : 105
    const timer = setInterval(() => {
      setWalkFrameIdx((prev) => (prev + 1) % WALK_FRAMES.length)
    }, intervalMs)

    return () => {
      clearInterval(timer)
      setWalkFrameIdx(0)
    }
  }, [isRunning, isWalking])

  const currentDisplaySrc = isWalking ? WALK_FRAMES[walkFrameIdx] : imgSrc

  const filterStyle = isCancelled
    ? 'grayscale(0.4) brightness(0.85) drop-shadow(0 8px 16px rgba(0,0,0,0.45))'
    : isError
    ? 'drop-shadow(0 0 16px rgba(239, 68, 68, 0.65)) drop-shadow(0 12px 20px rgba(0,0,0,0.45))'
    : isSuccess
    ? 'drop-shadow(0 0 20px rgba(52, 211, 153, 0.7)) drop-shadow(0 12px 20px rgba(0,0,0,0.45))'
    : isRunning
    ? 'drop-shadow(0 0 20px rgba(0, 212, 255, 0.7)) drop-shadow(0 12px 20px rgba(0,0,0,0.45))'
    : isWalking
    ? 'drop-shadow(0 0 16px rgba(0, 212, 255, 0.6)) drop-shadow(0 10px 18px rgba(0,0,0,0.4))'
    : isListening
    ? 'drop-shadow(0 0 22px rgba(0, 212, 255, 0.85)) drop-shadow(0 12px 20px rgba(0,0,0,0.45))'
    : isThinking
    ? 'drop-shadow(0 0 18px rgba(168, 85, 247, 0.6)) drop-shadow(0 12px 20px rgba(0,0,0,0.45))'
    : 'drop-shadow(0 14px 24px rgba(0, 0, 0, 0.5)) drop-shadow(0 0 20px rgba(0, 212, 255, 0.3))'

  const wrapperClass = [
    'avatar-char-wrap',
    'avatar-doraemon-wrap',
    `avatar-state-${state}`,
    className ?? '',
  ].join(' ')

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
            top: -16,
            right: 4,
            display: 'flex',
            alignItems: 'center',
            gap: 3,
            background: 'rgba(0, 212, 255, 0.22)',
            border: '1px solid rgba(0, 212, 255, 0.75)',
            borderRadius: 14,
            padding: '2px 8px',
            boxShadow: '0 0 16px rgba(0, 212, 255, 0.55)',
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
            top: -14,
            right: 8,
            display: 'flex',
            gap: 4,
            pointerEvents: 'none',
            zIndex: 10,
          }}
          aria-hidden="true"
        >
          <span style={{ fontSize: 15, filter: 'drop-shadow(0 2px 6px rgba(168, 85, 247, 0.5))' }}>💭</span>
        </div>
      )}

      {/* Success state: Sparkles and celebration stars */}
      {isSuccess && (
        <div
          className="doraemon-fx-success"
          style={{
            position: 'absolute',
            inset: -14,
            pointerEvents: 'none',
            zIndex: 10,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
          }}
          aria-hidden="true"
        >
          <span style={{ fontSize: 22, transform: 'rotate(-15deg)', filter: 'drop-shadow(0 0 8px #F59E0B)' }}>✨</span>
          <span style={{ fontSize: 24, transform: 'rotate(20deg)', filter: 'drop-shadow(0 0 10px #FBBF24)' }}>⭐</span>
        </div>
      )}

      {/* Running / Walking speed dash streaks */}
      {isWalking && (
        <div
          className="doraemon-fx-running"
          style={{
            position: 'absolute',
            bottom: 10,
            ...(facing === 'left' ? { right: -18, transform: 'scaleX(-1)' } : { left: -18 }),
            pointerEvents: 'none',
            zIndex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 3,
            opacity: isRunning ? 0.9 : 0.65,
          }}
          aria-hidden="true"
        >
          <div style={{ width: isRunning ? 32 : 20, height: 3, background: '#00D4FF', borderRadius: 2, boxShadow: '0 0 6px #00D4FF' }} />
          <div style={{ width: isRunning ? 22 : 14, height: 3, background: '#60A5FA', borderRadius: 2, marginLeft: 6 }} />
          <div style={{ width: isRunning ? 28 : 18, height: 3, background: '#93C5FD', borderRadius: 2 }} />
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
            boxShadow: '0 2px 8px rgba(245, 158, 11, 0.6)',
            zIndex: 10,
          }}
          aria-hidden="true"
        >
          !
        </div>
      )}

      {/* Error / Cancelled state: Sweat mark */}
      {(isError || isCancelled) && (
        <div
          className="doraemon-fx-error"
          style={{
            position: 'absolute',
            top: 2,
            right: 16,
            fontSize: 18,
            filter: 'drop-shadow(0 2px 6px rgba(239, 68, 68, 0.6))',
            pointerEvents: 'none',
            zIndex: 10,
          }}
          aria-hidden="true"
        >
          💧
        </div>
      )}

      {/* ── Doraemon Character Display (Walk frames or Idle Companion) ─── */}
      <div
        className="doraemon-character-stage"
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          filter: filterStyle,
          transition: 'filter 0.3s ease',
        }}
      >
        <img
          src={currentDisplaySrc}
          alt={`Doraemon companion — ${state}`}
          draggable={false}
          width={size}
          onError={() => {
            if (imgSrc === '/companion.webp') {
              setImgSrc('/companion.webp.png')
            }
          }}
          className={`doraemon-character-img ${isWalking ? 'doraemon-walking-img' : 'doraemon-idle-breathing'} ${facing === 'left' ? 'doraemon-facing-left' : 'doraemon-facing-right'}`}
          style={{
            display: 'block',
            width: size,
            height: 'auto',
            objectFit: 'contain',
            pointerEvents: 'none',
            userSelect: 'none',
            transform: facing === 'left' ? 'scaleX(-1)' : 'scaleX(1)',
            transition: isWalking ? 'none' : 'transform 0.22s ease',
          }}
        />
      </div>
    </div>
  )
}
