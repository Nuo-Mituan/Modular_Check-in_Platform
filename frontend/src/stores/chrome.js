import { ref } from 'vue'
import { defineStore } from 'pinia'
import { systemApi } from '@/api'

const DEFAULT_CHROME_VERSION = 156

export const useChromeStore = defineStore('chrome', () => {
  const chromeMajorVersion = ref(DEFAULT_CHROME_VERSION)
  const loaded = ref(false)
  const saving = ref(false)
  const degraded = ref(false)

  function normalize(value) {
    const number = Number(value)
    if (!Number.isInteger(number) || number < 1 || number > 999) return null
    return number
  }

  async function load() {
    if (loaded.value) return chromeMajorVersion.value
    const data = await systemApi.getChromeSettings()
    chromeMajorVersion.value = normalize(data.chrome_major_version) ?? DEFAULT_CHROME_VERSION
    degraded.value = Boolean(data.degraded)
    loaded.value = true
    return chromeMajorVersion.value
  }

  async function update(value) {
    const next = normalize(value)
    if (next === null) {
      throw new Error('Chrome 版本必须是 1-999 的整数')
    }
    saving.value = true
    try {
      const data = await systemApi.updateChromeSettings({ chrome_major_version: next })
      chromeMajorVersion.value = normalize(data.chrome_major_version) ?? next
      return data
    } finally {
      saving.value = false
    }
  }

  return { chromeMajorVersion, degraded, loaded, saving, load, update }
})
