// Icon type resolution is intentionally pure so it can be unit-tested without
// mounting Vue. Priority: legacy base64 fields, data URI, HTTPS, local file,
// then Emoji/text. Anything path-like but unsafe is a hard fallback to ⚠️.
import { isSupportedIconExtension } from '../constants/moduleIcon.js'

export const DATA_URI_RE = /^data:image\/(x-icon|png);base64,[A-Za-z0-9+/=]+$/
const UNSAFE_PATH_RE = /(^|[\\/])\.\.([\\/]|$)|\\|\0/

export const REMOTE_HTTP_ERROR = '远程地址使用 http:// 时仅允许本地或内网地址，公网请使用 https://'

// Frontend guard only; backend remains the security boundary.
export function isInsecureHostAllowed(hostname) {
  const host = String(hostname || '').toLowerCase().replace(/^\[|\]$/g, '')
  if (host === 'localhost') return true
  if (host === '::1') return true
  if (host.startsWith('::ffff:')) return false
  if (host.startsWith('fe80:') || host === '::') return false
  if (/^(fc|fd)[0-9a-f:]*$/.test(host)) return true
  if (/^127\./.test(host) || /^10\./.test(host) || /^192\.168\./.test(host)) return true
  const match = host.match(/^172\.(\d+)\./)
  if (match && Number(match[1]) >= 16 && Number(match[1]) <= 31) return true
  return false
}

export function classifyModuleIcon({ icon = '', source = 'url', iconData = '', moduleKey = '' } = {}) {
  const value = String(icon || '')
  const data = source === 'base64' ? String(iconData || '') : ''

  if (data) {
    return DATA_URI_RE.test(data) && data.length <= 65536
      ? { type: 'base64', src: data }
      : { type: 'fallback', src: '' }
  }
  if (value.startsWith('data:')) {
    return DATA_URI_RE.test(value) && value.length <= 65536
      ? { type: 'base64', src: value }
      : { type: 'fallback', src: '' }
  }
  if (/^https?:\/\//i.test(value)) {
    try {
      const parsed = new URL(value)
      if (parsed.protocol === 'http:' && !isInsecureHostAllowed(parsed.hostname)) {
        return { type: 'fallback', src: '', reason: REMOTE_HTTP_ERROR }
      }
      // Dotted last segments (e.g. /assets/1.2) are conservatively treated as
      // extensions and fall back unless supported; this is intentional.
      const hasExtension = /\.[A-Za-z0-9]+$/.test(parsed.pathname)
      if (hasExtension && !isSupportedIconExtension(parsed.pathname)) {
        return { type: 'fallback', src: '' }
      }
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

export function moduleIconUrl(key, path = 'icon.ico') {
  const base = String(import.meta.env?.VITE_API_BASE || '/api').replace(/\/+$/, '')
  return `${base}/modules/icon?key=${encodeURIComponent(key)}&path=${encodeURIComponent(path)}`
}
