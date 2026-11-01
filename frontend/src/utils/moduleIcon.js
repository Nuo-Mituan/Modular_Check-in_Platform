// Icon type resolution is intentionally pure so it can be unit-tested without
// mounting Vue. Priority: legacy base64 fields, data URI, HTTPS, local file,
// then Emoji/text. Anything path-like but unsafe is a hard fallback to ⚠️.
import { ICON_UNSUPPORTED_DETAIL, isSupportedIconExtension } from '../constants/moduleIcon.js'

export const DATA_URI_RE = /^data:image\/(x-icon|png|jpeg|gif|webp);base64,[A-Za-z0-9+/=]+$/
function dataUriMagicOk(value) {
  try {
    const [head, body] = String(value).split(',', 2)
    const mime = head.slice(5).split(';')[0].toLowerCase()
    const raw = atob(body)
    const b = Uint8Array.from(raw, (c) => c.charCodeAt(0))
    const png = b[0]===0x89&&b[1]===0x50&&b[2]===0x4e&&b[3]===0x47
    const jpg = b[0]===0xff&&b[1]===0xd8&&b[2]===0xff
    const gif = b[0]===0x47&&b[1]===0x49&&b[2]===0x46
    const webp = b[0]===0x52&&b[1]===0x49&&b[2]===0x46&&b[3]===0x46&&b[8]===0x57&&b[9]===0x45&&b[10]===0x42&&b[11]===0x50
    const ico = b[0]===0&&b[1]===0&&b[2]===1&&b[3]===0
    return (mime==='image/png'&&png)||(mime==='image/jpeg'&&jpg)||(mime==='image/gif'&&gif)||(mime==='image/webp'&&webp)||((mime==='image/x-icon')&&ico)
  } catch { return false }
}

const UNSAFE_PATH_RE = /(^|[\\/])\.\.([\\/]|$)|\\|\0/

// Mirror of REMOTE_HTTP_ERROR in backend/app/services/remote_url.py (TD-31 unification).
export const REMOTE_HTTP_ERROR = '远程地址使用 http:// 时仅允许本地或内网地址，公网请使用 https://'

function rawAuthority(value) {
  const match = String(value).match(/^[a-z][a-z0-9+.-]*:\/\/([^/?#]*)/i)
  return match ? match[1] : ''
}

function hasIncompleteIpLiteral(value) {
  const authority = rawAuthority(value)
  if (authority.includes('@')) return true
  let host = authority.replace(/^.*@/, '')
  if (host.startsWith('[')) return false
  host = host.replace(/:\d+$/, '')
  if (!/^\d[\d.]*$/.test(host)) return false
  const parts = host.split('.')
  return !(parts.length === 4 && parts.every((part) => /^\d{1,3}$/.test(part) && Number(part) <= 255))
}

// Frontend guard only; backend remains the security boundary.
export function isInsecureHostAllowed(hostname) {
  const host = String(hostname || '').toLowerCase().replace(/^\[|\]$/g, '')
  if (host === 'localhost' || host === '::1') return true
  if (host.endsWith('.')) return false
  if (host.startsWith('::ffff:')) return false
  if (host.startsWith('fe80:') || host === '::') return false
  if (/^(fc|fd)[0-9a-f:]+$/.test(host)) return true
  const parts = host.split('.')
  if (parts.length !== 4) return false
  if (!parts.every((part) => /^\d{1,3}$/.test(part) && Number(part) <= 255)) return false
  if (Number(parts[0]) === 127) return true
  if (Number(parts[0]) === 10) return true
  if (Number(parts[0]) === 192 && Number(parts[1]) === 168) return true
  return Number(parts[0]) === 172 && Number(parts[1]) >= 16 && Number(parts[1]) <= 31
}

export function classifyModuleIcon({ icon = '', source = 'url', iconData = '', moduleKey = '' } = {}) {
  const value = String(icon || '')
  const data = source === 'base64' ? String(iconData || '') : ''

  if (data) {
    return DATA_URI_RE.test(data) && data.length <= 262144 && dataUriMagicOk(data)
      ? { type: 'base64', src: data }
      : { type: 'fallback', src: '' }
  }
  if (value.startsWith('data:')) {
    return DATA_URI_RE.test(value) && value.length <= 262144 && dataUriMagicOk(value)
      ? { type: 'base64', src: value }
      : { type: 'fallback', src: '' }
  }
  if (/^https?:\/\//i.test(value)) {
    try {
      const parsed = new URL(value)
      if (parsed.protocol === 'http:' && (hasIncompleteIpLiteral(value) || !isInsecureHostAllowed(parsed.hostname))) {
        return { type: 'fallback', src: '', reason: REMOTE_HTTP_ERROR }
      }
      // Remote content is validated by the same-origin proxy via magic bytes;
      // the URL extension is intentionally not a rendering gate (GIF/WebP).
      return { type: 'remote-url', src: value }
    } catch {
      return { type: 'fallback', src: '' }
    }
  }

  // Public static paths are safe to use as-is. Other absolute paths are not
  // allowed to reach the module filesystem endpoint.
  if (value.startsWith('/')) {
    return value.startsWith('/static/') && isSupportedIconExtension(value)
      ? { type: 'local-path', src: value, path: value }
      : { type: 'fallback', src: '' }
  }

  const looksLocal =
    value.startsWith('./') || value.includes('/') || isSupportedIconExtension(value)
  if (looksLocal) {
    if (
      !moduleKey ||
      UNSAFE_PATH_RE.test(value) ||
      (/\.[A-Za-z0-9]+$/.test(value) && !isSupportedIconExtension(value))
    ) {
      return { type: 'fallback', src: '' }
    }
    const relative = value.startsWith('./') ? value.slice(2) : value
    return relative
      ? { type: 'local-path', path: relative }
      : { type: 'fallback', src: '' }
  }

  if (source === 'local' && moduleKey) return { type: 'local-path', path: 'icon.ico' }

  // A colon/other protocol-like string that reached here is not a safe URL.
  if (value.includes('://') || value.startsWith(':') || value.includes('::')) {
    return { type: 'fallback', src: '' }
  }
  return { type: 'emoji', src: '' }
}

export function isImageContentType(value = '') {
  return /^image\//i.test(String(value))
}

export function remoteIconUrl(moduleId) {
  const base = String(import.meta.env?.VITE_API_BASE || '/api').replace(/\/+$/, '')
  return `${base}/modules/${encodeURIComponent(moduleId)}/icon`
}

export function moduleIconUrl(key, path = 'icon.ico') {
  const base = String(import.meta.env?.VITE_API_BASE || '/api').replace(/\/+$/, '')
  return `${base}/modules/icon?key=${encodeURIComponent(key)}&path=${encodeURIComponent(path)}`
}
