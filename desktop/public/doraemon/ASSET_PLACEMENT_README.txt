/**
 * DORAEMON ASSET PLACEMENT GUIDE
 * ================================
 *
 * FILE: desktop/public/doraemon/
 *
 * ⚠️  PLACEHOLDER NOTICE — LICENSED ASSET REQUIRED BEFORE PRODUCTION
 * =====================================================================
 *
 * The Doraemon character is a registered trademark and copyrighted work
 * owned by Fujiko Pro / Shogakukan / TV Asahi / ADK Emotions, Inc.
 * No free or Creative Commons license is available for this character.
 *
 * To use the real Doraemon character in this application you MUST:
 *   1. Obtain a written license from Fujiko Pro or a sub-licensor.
 *   2. Or use an officially distributed, royalty-free asset package
 *      that explicitly covers digital software applications.
 *   3. Confirm the license covers your territory and use case
 *      (non-commercial / commercial / educational).
 *
 * HOW TO REPLACE THIS PLACEHOLDER
 * ---------------------------------
 * Place your licensed Doraemon sprite assets in this folder:
 *
 *   desktop/public/doraemon/
 *   ├── idle.webp        (or idle.png / idle.gif)
 *   ├── thinking.webp
 *   ├── running.webp     (spritesheet or animated)
 *   ├── success.webp
 *   ├── error.webp
 *   ├── approval.webp    (waiting for approval state)
 *   └── cancelled.webp
 *
 * Then edit desktop/src/AvatarCharacter.tsx:
 *   - Set ASSET_MODE = 'sprite' instead of 'svg-placeholder'
 *   - The component will automatically load images from /doraemon/<state>.webp
 *
 * UNTIL THEN:
 * The application uses an original flat-vector SVG character (src/AvatarCharacter.tsx)
 * as a development placeholder. It is labeled clearly in the UI and in code.
 * The SVG character is an ORIGINAL DESIGN and does not reproduce Doraemon's trade dress.
 */

