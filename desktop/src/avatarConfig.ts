/**
 * AVATAR SIZING CONFIGURATION
 * ============================
 * Centralized, proportional dimensions for Doraemon desktop companion.
 * Ensures character maintains authentic anime aspect ratio (280x380 ~ 1:1.35)
 * without stretching, distortion, or covering desktop/taskbar icons.
 */

export interface AvatarDimensions {
  /** Rendered width of Doraemon character in pixels */
  characterWidth: number
  /** Width of the transparent BrowserWindow in standalone avatar mode */
  windowWidth: number
  /** Height of the transparent BrowserWindow in standalone avatar mode */
  windowHeight: number
  /** Width of the BrowserWindow when floating chatbox is expanded */
  chatboxWidth: number
  /** Height of the BrowserWindow when floating chatbox is expanded */
  chatboxHeight: number
}

export const AVATAR_CONFIG: AvatarDimensions = {
  characterWidth: 108,
  windowWidth: 196,
  windowHeight: 200,
  chatboxWidth: 580,
  chatboxHeight: 520,
}

export default AVATAR_CONFIG
