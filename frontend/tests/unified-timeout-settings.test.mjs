import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const component = readFileSync(
  new URL('../src/components/UnifiedTimeoutSettings.vue', import.meta.url),
  'utf8',
)

test('timeout switch save uses the change event value, not stale prop', () => {
  assert.match(component, /@change="saveEnabled"/)
  assert.match(component, /function saveEnabled\(value\)/)
  assert.match(component, /const enabled = Boolean\(value\)/)
  assert.match(component, /emit\('save', \{ enabled, time: timeModel\.value \}\)/)
})

test('time picker save preserves current enabled value', () => {
  assert.match(component, /@change="saveTime"/)
  assert.match(component, /function saveTime\(value\)/)
  assert.match(component, /enabled: enabledModel\.value, time/)
})


test('parent does not report success when backend keeps disabled', () => {
  const view = readFileSync(new URL('../src/views/PushCenterView.vue', import.meta.url), 'utf8')
  assert.match(view, /Boolean\(data\.timeout_enabled\) !== requestedEnabled/)
  assert.match(view, /超时推送设置未生效/)
  assert.match(view, /catch \{\s*await loadTimeoutSettings/)
  assert.doesNotMatch(view, /catch \{[^}]*ElMessage\.success/)
})
