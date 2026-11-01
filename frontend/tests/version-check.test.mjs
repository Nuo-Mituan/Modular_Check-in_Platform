import test from 'node:test'
import assert from 'node:assert/strict'
import { compareVersions, shouldUpdate } from '../src/utils/versionCheck.js'

test('version comparison handles equality and patch/minor/major', () => {
  assert.equal(compareVersions('1.0.7', '1.0.7'), 0)
  assert.equal(compareVersions('1.0.7', '1.0.6'), 1)
  assert.equal(compareVersions('1.1.0', '1.0.9'), 1)
  assert.equal(compareVersions('2.0.0', '1.9.9'), 1)
})

test('invalid versions fail open', () => {
  assert.deepEqual(shouldUpdate('bad', { version: '1.0.7' }), { action: 'none', reason: 'invalid version' })
})

test('equal version is none', () => {
  assert.equal(shouldUpdate('1.0.7', { version: '1.0.7', recommended: true }).action, 'none')
})

test('newer recommended version recommends', () => {
  assert.equal(shouldUpdate('1.0.6', { version: '1.0.7', recommended: true }).action, 'recommend')
})

test('below minimum forces update', () => {
  assert.equal(shouldUpdate('1.0.4', { version: '1.0.7', min_supported_client: '1.0.5', recommended: true }).action, 'force')
})

test('newer non-recommended is optional none', () => {
  assert.equal(shouldUpdate('1.0.6', { version: '1.0.7', recommended: false }).action, 'none')
})
