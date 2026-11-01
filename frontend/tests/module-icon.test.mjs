import test from 'node:test'
import assert from 'node:assert/strict'
import { classifyModuleIcon, isImageContentType, moduleIconUrl } from '../src/utils/moduleIcon.js'
import { isSupportedIconExtension } from '../src/constants/moduleIcon.js'


const key = 'demo_checkin'
const cases = [
  ['./favicon.ico', 'local-path'],
  ['favicon.ico', 'local-path'],
  ['icons/logo.png', 'local-path'],
  ['/static/icon.svg', 'fallback'],
  ['🚀', 'emoji'],
  ['https://example.com/a.png', 'remote-url'],
  ['data:image/png;base64,iVBORw0KGgo=', 'base64'],
  ['invalid::path', 'fallback'],
]

for (const [icon, expected] of cases) {
  test(`classifies ${icon} as ${expected}`, () => {
    const kind = classifyModuleIcon({ icon, moduleKey: key })
    assert.equal(kind.type, expected)
    if (expected === 'local-path') {
      assert.ok(kind.path, 'local path must be present')
      assert.equal(kind.path.includes('..'), false)
    }
  })
}

test('blocks traversal and absolute secret paths', () => {
  for (const icon of ['../etc/passwd', './../../secret.ico', '/var/www/favicon.ico', '..\\secret.ico']) {
    assert.equal(classifyModuleIcon({ icon, moduleKey: key }).type, 'fallback')
  }
})

test('legacy base64 source and local fallback stay compatible', () => {
  assert.equal(
    classifyModuleIcon({ icon: 'ignored', source: 'base64', iconData: 'data:image/png;base64,AAAA', moduleKey: key }).type,
    'base64',
  )
  assert.equal(classifyModuleIcon({ icon: '🎯', source: 'local', moduleKey: key }).type, 'local-path')
})

test('accepts image content types only', () => {
  assert.equal(isImageContentType('image/png'), true)
  assert.equal(isImageContentType('image/x-icon'), true)
  assert.equal(isImageContentType('application/json'), false)
  assert.equal(isImageContentType(''), false)
})

test('builds module icon URL without depending on API object methods', () => {
  assert.equal(
    moduleIconUrl('demo_checkin', 'favicon.ico'),
    '/api/modules/icon?key=demo_checkin&path=favicon.ico',
  )
})

test('unsupported local extensions fall back without a network request', () => {
  assert.equal(
    classifyModuleIcon({ icon: './favicon.gif', moduleKey: key }).type,
    'fallback',
  )
})


test('SVG extension is not supported and SVG data URI is rejected', () => {
  assert.equal(isSupportedIconExtension('icon.svg'), false)
  assert.equal(classifyModuleIcon({ icon: 'data:image/svg+xml;base64,AAAA', moduleKey: key }).type, 'fallback')
})

test('remote URL classification delegates content type to the proxy', () => {
  for (const icon of [
    'https://example.com/icon.svg',
    'https://example.com/icon.svg?v=2',
    'https://example.com/icon.gif',
    'https://example.com/icon.png',
  ]) {
    assert.equal(classifyModuleIcon({ icon, moduleKey: key }).type, 'remote-url')
  }
  assert.equal(
    classifyModuleIcon({ icon: 'http://example.com/icon.png', moduleKey: key }).type,
    'fallback',
  )
})

test('http remote URL allows only literal local/private hosts', () => {
  for (const icon of [
    'http://localhost:8080/icon.png',
    'http://LOCALHOST:8080/icon.png',
    'http://127.0.0.1/icon.png',
    'http://10.1.2.3/icon.png',
    'http://172.16.0.1/icon.png',
    'http://192.168.1.1/icon.png',
    'http://[::1]/icon.png',
    'http://[fd00::1]/icon.png',
  ]) assert.equal(classifyModuleIcon({ icon }).type, 'remote-url', icon)
  for (const icon of [
    'http://example.com/icon.png',
    'http://169.254.1.1/icon.png',
    'http://[::ffff:10.0.0.1]/icon.png',
    'http://0.0.0.0/icon.png',
    'http://[::]/icon.png',
    'http://localhost./icon.png',
    'http://10./icon.png',
    'http://192.168.1/icon.png',
    'http://127.1/icon.png',
    'http://evil.com@127.0.0.1/icon.png',
  ]) assert.equal(classifyModuleIcon({ icon }).type, 'fallback', icon)
  assert.equal(
    classifyModuleIcon({ icon: 'http://example.com/icon.png' }).reason,
    '远程地址使用 http:// 时仅允许本地或内网地址，公网请使用 https://',
  )
})
