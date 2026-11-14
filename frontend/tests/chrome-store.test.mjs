import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mocks = vi.hoisted(() => ({
  getChromeSettings: vi.fn(),
  updateChromeSettings: vi.fn(),
}))

vi.mock('@/api', () => ({ systemApi: mocks }))

import { useChromeStore } from '@/stores/chrome'

describe('chrome store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mocks.getChromeSettings.mockReset()
    mocks.updateChromeSettings.mockReset()
  })

  it('force reload refreshes version and degraded', async () => {
    const store = useChromeStore()
    mocks.getChromeSettings.mockResolvedValue({ chrome_major_version: 120, degraded: false })
    await store.load()
    mocks.getChromeSettings.mockResolvedValue({ chrome_major_version: 121, degraded: true })
    await store.load(true)
    expect(store.chromeMajorVersion).toBe(121)
    expect(store.degraded).toBe(true)
  })

  it('clears degraded after a successful save', async () => {
    const store = useChromeStore()
    store.degraded = true
    mocks.updateChromeSettings.mockResolvedValue({ chrome_major_version: 120, degraded: false })
    await store.update(120)
    expect(store.chromeMajorVersion).toBe(120)
    expect(store.degraded).toBe(false)
  })
})
