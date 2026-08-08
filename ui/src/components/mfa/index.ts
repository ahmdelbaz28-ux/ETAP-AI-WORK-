/**
 * MFA components — Two-Factor Authentication UI.
 *
 * Issue #12: QR code accessibility + toast prefix deduplication.
 *
 * - MFASetup: Full TOTP setup flow (QR code + verify)
 *
 * Accessibility features:
 * - QR code: role="img" + descriptive aria-label
 * - Manual secret key fallback with copy-to-clipboard
 * - Error announcements: role="alert" + aria-live="assertive"
 * - Screen-reader-only live region for step transitions
 * - All inputs have associated <label> elements
 */

export { MFASetup } from "./MFASetup";
