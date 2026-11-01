import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ModuleIcon from '../src/components/ModuleIcon.vue'

const blob = new Blob(['png'], { type: 'image/png' })
const BLOB_URL = 'blob:mock-icon'
let createObjectURL
let revokeObjectURL

beforeEach(() => {
  createObjectURL = vi.fn(() => BLOB_URL)
  revokeObjectURL = vi.fn()
  Object.defineProperty(URL, 'createObjectURL', { value: createObjectURL, configurable: true })
  Object.defineProperty(URL, 'revokeObjectURL', { value: revokeObjectURL, configurable: true })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  delete URL.createObjectURL
  delete URL.revokeObjectURL
})

describe('ModuleIcon component', () => {
  it('renders base64 icon as img', () => {
    const wrapper = mount(ModuleIcon, {
      props: { icon: 'data:image/png;base64,iVBORw0KGgo=' },
    })
    expect(wrapper.find('img').exists()).toBe(true)
    expect(wrapper.find('img').attributes('src')).toContain('data:image/png')
    expect(wrapper.classes()).toContain('module-icon')
  })

  it('falls back for missing/unsupported props', () => {
    const wrapper = mount(ModuleIcon)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text().length).toBeGreaterThan(0)
  })

  it('shows fallback after image error', async () => {
    const wrapper = mount(ModuleIcon, {
      props: { icon: 'data:image/png;base64,iVBORw0KGgo=' },
    })
    await wrapper.find('img').trigger('error')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('⚠️')
  })

  it('loads remote icon through proxy and revokes object URL', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      blob: async () => blob,
    })))
    const wrapper = mount(ModuleIcon, {
      props: { icon: 'https://example.com/icon.png', moduleId: 7 },
    })
    await flushPromises()
    expect(fetch).toHaveBeenCalledWith('/api/modules/7/icon', { credentials: 'include' })
    expect(wrapper.find('img').attributes('src')).toBe(BLOB_URL)
    wrapper.unmount()
    expect(revokeObjectURL).toHaveBeenCalledWith(BLOB_URL)
  })

  it('falls back when moduleId is missing for remote icon', async () => {
    const wrapper = mount(ModuleIcon, {
      props: { icon: 'https://example.com/icon.png' },
    })
    await flushPromises()
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.attributes('title')).toBe('no-module-id')
  })
})
