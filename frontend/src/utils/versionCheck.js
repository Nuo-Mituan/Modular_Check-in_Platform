export function parseVersion(value) {
  const match = String(value || '').trim().match(/^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$/)
  if (!match) return null
  return [Number(match[1]), Number(match[2]), Number(match[3]), match[4] || '']
}

export function compareVersions(a, b) {
  const left = parseVersion(a)
  const right = parseVersion(b)
  if (!left || !right) return null
  for (let i = 0; i < 3; i += 1) {
    if (left[i] !== right[i]) return left[i] > right[i] ? 1 : -1
  }
  if (!left[3] && right[3]) return 1
  if (left[3] && !right[3]) return -1
  return left[3] === right[3] ? 0 : (left[3] > right[3] ? 1 : -1)
}

export function shouldUpdate(current, info = {}) {
  if (compareVersions(info.version, current) === null || parseVersion(current) === null) {
    return { action: 'none', reason: 'invalid version' }
  }
  if (compareVersions(info.version, current) <= 0) return { action: 'none', reason: 'already up to date' }
  if (info.min_supported_client && compareVersions(current, info.min_supported_client) < 0) {
    return { action: 'force', reason: 'below min_supported_client' }
  }
  return info.recommended
    ? { action: 'recommend', reason: 'recommended update' }
    : { action: 'none', reason: 'optional update' }
}
