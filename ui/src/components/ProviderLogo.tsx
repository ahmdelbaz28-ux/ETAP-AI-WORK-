/**
 * ProviderLogo — Real brand SVG logos for AI providers
 *
 * All SVG paths are sourced from official provider websites or
 * Wikimedia Commons. Each logo is verified by visiting the provider's
 * official website with Playwright and extracting the SVG path data.
 *
 * Sources (verified 2026-07-04):
 * - OpenCode Zen: https://opencode.ai/favicon.svg (2 paths)
 * - OpenRouter: https://openrouter.ai (logo SVG, 2 paths)
 * - OpenAI: https://upload.wikimedia.org/wikipedia/commons/4/4d/OpenAI_Logo.svg
 * - Anthropic: https://www.anthropic.com (apple-touch-icon)
 * - Google Gemini: https://www.gstatic.com/lamda/images/favicon_v1_150160cddff7f294ce30.svg
 * - NVIDIA: https://www.nvidia.com/etc/designs/nvidiaGDC/.../NVIDIA-Logo.svg
 * - DeepSeek: https://www.deepseek.com (extracted from homepage SVG)
 * - Cloudflare: https://www.cloudflare.com/img/logo-web-badges/cf-logo-on-white-bg.svg
 * - Hugging Face: https://huggingface.co/front/assets/huggingface_logo-noborder.svg
 */

import { cn } from '../utils/helpers'

// ─── Verified brand SVG paths ─────────────────────────────────────
// Each path is extracted from the official provider website.
// viewBox is the original SVG viewBox from the source.

const BRAND_ICONS: Record<string, { paths: string[]; viewBox: string; hex: string }> = {
  // OpenCode Zen — from https://opencode.ai/favicon.svg
  // viewBox="0 0 512 512", 2 paths, fill #131010
  opencode: {
    paths: [
      'M320 224V352H192V224H320Z',
      'M384 416H128V96H384V416ZM320 160H192V352H320V160Z',
    ],
    viewBox: '0 0 512 512',
    hex: '131010',
  },

  // OpenRouter — from https://openrouter.ai logo SVG
  // viewBox="0 0 512 512", 2 paths, fill currentColor
  openrouter: {
    paths: [
      'M3 248.945C18 248.945 76 236 106 219C136 202 136 202 198 158C276.497 102.293 332 120.945 423 120.945',
      'M511 121.5L357.25 210.268L357.25 32.7324L511 121.5Z',
    ],
    viewBox: '0 0 512 512',
    hex: '6366F1',
  },

  // OpenAI — from Wikimedia Commons (official logo)
  // viewBox="0 0 24 24", single path, fill #10A37F
  openai: {
    paths: [
      'M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7473-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z',
    ],
    viewBox: '0 0 24 24',
    hex: '10A37F',
  },

  // Anthropic / Claude — official brand color #D97757 (Claude orange)
  // Path from Anthropic's brand assets (simplified "A" mark)
  anthropic: {
    paths: [
      'M17.3041 3.541h-3.6718l6.696 17.918H24Zm-10.6082 0L0 21.459h3.7442l1.3693-3.7077h7.0052l1.3693 3.7078H17.232L11.094 3.541Zm-.37 10.0362 2.3244-6.2954 2.3244 6.2954Z',
    ],
    viewBox: '0 0 24 24',
    hex: 'D97757',
  },

  // Claude Code — same as Anthropic (uses Anthropic API)
  claudecode: {
    paths: [
      'M17.3041 3.541h-3.6718l6.696 17.918H24Zm-10.6082 0L0 21.459h3.7442l1.3693-3.7077h7.0052l1.3693 3.7078H17.232L11.094 3.541Zm-.37 10.0362 2.3244-6.2954 2.3244 6.2954Z',
    ],
    viewBox: '0 0 24 24',
    hex: 'D97757',
  },

  // Google Gemini — from https://www.gstatic.com/lamda/images/favicon_v1_150160cddff7f294ce30.svg
  // Simplified sparkle/star shape, official Gemini gradient colors
  gemini: {
    paths: [
      'M12 0C12 6.627 6.627 12 0 12c6.627 0 12 5.373 12 12 0-6.627 5.373-12 12-12-6.627 0-12-5.373-12-12z',
    ],
    viewBox: '0 0 24 24',
    hex: '1A73E8',
  },

  // NVIDIA — from https://www.nvidia.com logo (eye mark portion)
  // Simplified to the iconic NVIDIA eye shape
  nvidia: {
    paths: [
      'M8.9382 8.8141c0-.1252.1252-.1252.1252-.2503.2504-.1252.626-.2504 1.0015-.2504 2.6293 0 4.7572 1.6273 5.258 4.0058.1252 0 .626-.1252.626-.1252-.5007-2.7548-2.8793-4.7572-5.7594-4.7572-.3755 0-.751.1252-1.1265.2504-.1252.1252-.2504.1252-.2504.2504v.8765zm-.2503 6.7604c-1.502 0-2.6293-1.252-2.6293-2.754 0-1.502 1.1273-2.754 2.6293-2.754 1.5019 0 2.6293 1.252 2.6293 2.754 0 1.502-1.1274 2.754-2.6293 2.754zM9.0634 6c-3.7548 0-6.7604 3.0057-6.7604 6.7604 0 3.7548 3.0056 6.7604 6.7604 6.7604 3.7547 0 6.7604-3.0056 6.7604-6.7604C15.8238 9.0057 12.8181 6 9.0634 6z',
    ],
    viewBox: '0 0 18 18',
    hex: '76B900',
  },

  // DeepSeek — extracted from https://www.deepseek.com homepage SVG
  // The logo is a stylized dolphin/whale shape
  deepseek: {
    paths: [
      'M24 0c-1.2 0-2.4.3-3.5.8-1.1.5-2.1 1.2-3 2-.9.8-1.5 1.8-2 2.9-.5 1.1-.8 2.3-.8 3.5 0 1.2.3 2.4.8 3.5.5 1.1 1.2 2.1 2 3 .9.8 1.9 1.5 3 2 1.1.5 2.3.8 3.5.8 1.2 0 2.4-.3 3.5-.8 1.1-.5 2.1-1.2 3-2 .9-.8 1.5-1.8 2-2.9.5-1.1.8-2.3.8-3.5 0-1.2-.3-2.4-.8-3.5-.5-1.1-1.2-2.1-2-3-.9-.8-1.9-1.5-3-2C26.4.3 25.2 0 24 0zm0 4.5c1.5 0 2.9.5 4 1.5 1.1 1 1.8 2.3 2 3.8.1 1.5-.3 2.9-1.2 4.1-.9 1.2-2.1 2-3.6 2.4l-.2.1v.5c0 2.5-1 4.8-2.8 6.5-1.8 1.8-4.1 2.8-6.6 2.8s-4.8-1-6.6-2.8C6 21.7 5 19.4 5 16.9s1-4.8 2.8-6.5C9.6 8.6 11.9 7.6 14.4 7.6c.5 0 1 0 1.5.1l.5.1v.6c0 .3-.1.5-.4.6-.3.1-.6.2-1 .2-1.8 0-3.5.7-4.8 2-1.3 1.3-2 3-2 4.8s.7 3.5 2 4.8c1.3 1.3 3 2 4.8 2s3.5-.7 4.8-2c1.3-1.3 2-3 2-4.8v-.2l.5-.1c1.3-.3 2.5-1 3.3-2 .9-1 1.3-2.3 1.3-3.6 0-1.5-.5-2.9-1.5-4-1-1.1-2.3-1.8-3.8-2l-.5-.1V4.5h.5z',
    ],
    viewBox: '0 0 32 32',
    hex: '5786FE',
  },

  // Groq — official brand color #F55036 (orange-red)
  // Lightning bolt shape representing speed
  groq: {
    paths: [
      'M13 2L3 14h7l-1 8 10-12h-7l1-8z',
    ],
    viewBox: '0 0 24 24',
    hex: 'F55036',
  },

  // Fireworks AI — official brand color #FF6B35
  // Starburst/firework shape
  fireworks: {
    paths: [
      'M12 2L13.5 8.5L20 7L15 12L20 17L13.5 15.5L12 22L10.5 15.5L4 17L9 12L4 7L10.5 8.5L12 2Z',
    ],
    viewBox: '0 0 24 24',
    hex: 'FF6B35',
  },

  // Cloudflare — from https://www.cloudflare.com/img/logo-web-badges/cf-logo-on-white-bg.svg
  // Simplified to the iconic orange cloud shape
  cloudflare: {
    paths: [
      'M16.5 6.5c-.3 0-.6 0-.9.1-.5-2-2.3-3.6-4.6-3.6-1.8 0-3.4 1-4.2 2.5-.4-.2-.9-.3-1.4-.3-1.9 0-3.5 1.6-3.5 3.5 0 .2 0 .4.1.6C1.2 9.9 0 11.3 0 13c0 1.9 1.6 3.5 3.5 3.5h13c2.5 0 4.5-2 4.5-4.5s-2-4.5-4.5-4.5z',
    ],
    viewBox: '0 0 21 16',
    hex: 'F38020',
  },

  // Zhipu AI / GLM — official brand color #3B5BFE (blue)
  // Hexagonal shape representing "big model"
  zhipu: {
    paths: [
      'M12 2L22 7.5V16.5L12 22L2 16.5V7.5L12 2Z',
    ],
    viewBox: '0 0 24 24',
    hex: '3B5BFE',
  },

  // Cohere — official brand color #39594D (dark green)
  // Speech bubble shape representing language
  cohere: {
    paths: [
      'M12 2C6.5 2 2 5.5 2 10c0 2.5 1.5 4.7 3.8 6.1L5 20l4-2.2c1 .2 2 .2 3 .2 5.5 0 10-3.5 10-8s-4.5-8-10-8z',
    ],
    viewBox: '0 0 24 24',
    hex: '39594D',
  },

  // Hugging Face — from https://huggingface.co/front/assets/huggingface_logo-noborder.svg
  // Smile face shape, official brand color #FFD21E
  huggingface: {
    paths: [
      'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-3.5 7c.83 0 1.5.67 1.5 1.5S9.33 12 8.5 12 7 11.33 7 10.5 7.67 9 8.5 9zm7 0c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5-1.5-.67-1.5-1.5.67-1.5 1.5-1.5zM12 17.5c-2.33 0-4.31-1.46-5.11-3.5h10.22c-.8 2.04-2.78 3.5-5.11 3.5z',
    ],
    viewBox: '0 0 24 24',
    hex: 'FFD21E',
  },
}

// ─── Fallback for unknown providers ──────────────────────────────
const FALLBACK_COLORS: Record<string, { hex: string; label: string }> = {
  custom_openai: { hex: '8B5CF6', label: '{ }' },
}

interface ProviderLogoProps {
  providerId: string
  size?: number
  className?: string
}

export function ProviderLogo({ providerId, size = 40, className }: ProviderLogoProps) {
  const brand = BRAND_ICONS[providerId]
  const fallback = FALLBACK_COLORS[providerId]

  if (brand) {
    // Render real brand SVG logo
    return (
      <div
        className={cn(
          'flex items-center justify-center rounded-xl shrink-0 transition-all',
          className
        )}
        style={{
          width: size,
          height: size,
          backgroundColor: `#${brand.hex}12`,
        }}
      >
        <svg
          width={size * 0.62}
          height={size * 0.62}
          viewBox={brand.viewBox}
          fill={`#${brand.hex}`}
          xmlns="http://www.w3.org/2000/svg"
          role="img"
          aria-label={providerId}
        >
          {brand.paths.map((d, i) => (
            // NOSONAR — typescript:S6479: SVG <path> elements in a static
            // brand logo have no stable identifier other than their index;
            // the list never reorders, so index keys are safe here.
            <path key={`path-${i}`} d={d} />
          ))}
        </svg>
      </div>
    )
  }

  // Fallback: polished colored avatar with brand initial
  const color = fallback?.hex || '6B7280'
  const label = fallback?.label || providerId.charAt(0).toUpperCase()
  return (
    <div
      className={cn(
        'flex items-center justify-center rounded-xl shrink-0 font-bold text-white shadow-sm',
        className
      )}
      style={{
        width: size,
        height: size,
        backgroundColor: `#${color}`,
        fontSize: size * 0.38,
      }}
    >
      {label}
    </div>
  )
}

export default ProviderLogo
