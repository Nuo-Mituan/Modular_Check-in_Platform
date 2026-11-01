// Mirror of backend/app/services/icon_policy.py; backend is the security boundary.
export const ICON_ALLOWED = Object.freeze(['ico', 'png', 'jpeg', 'gif', 'webp'])
// Single source of truth for local module icon formats.
// `jpg` is an extension alias; backend SUFFIX_TO_FORMAT maps it to jpeg.
export const ICON_EXTENSIONS = Object.freeze([
  'ico', 'png', 'jpg', 'jpeg', 'gif', 'webp',
])

export const ICON_UNSUPPORTED_DETAIL = '图标仅支持 PNG/JPEG/GIF/WebP/ICO，不支持 SVG'
export const ICON_EXT_RE = new RegExp(
  `\\.(${ICON_EXTENSIONS.map((ext) => (ext === 'jpg' ? 'jpe?g' : ext)).join('|')})$`,
  'i',
)

export function isSupportedIconExtension(value = '') {
  return ICON_EXT_RE.test(value)
}

/** True for path-like input; does NOT imply the extension is supported. */
export function looksLikeLocalPath(value = '') {
  return /[\\/]/.test(value) || isSupportedIconExtension(value)
}
