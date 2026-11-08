<template>
  <div class="chrome-sync" :class="{ disabled: !supported }">
    <div class="chrome-sync-copy">
      <strong>同步全局 Chrome 版本</strong>
      <span v-if="supported">开启后，全局版本变更会自动写入本模块并保存。</span>
      <span v-else>该模块不支持自定义 Chrome 版本。</span>
    </div>
    <el-tooltip
      :disabled="supported"
      content="该模块不支持自定义 Chrome 版本"
      placement="top"
    >
      <span>
        <el-switch
          v-model="enabled"
          :disabled="!supported || loading"
          :loading="loading || saving"
          @change="handleChange"
        />
      </span>
    </el-tooltip>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useChromeStore } from '@/stores/chrome'
import { modulesApi } from '@/api'

const props = defineProps({
  moduleId: { type: Number, required: true },
  supported: { type: Boolean, default: false },
})
const emit = defineEmits(['version', 'update:enabled'])
const chrome = useChromeStore()
const enabled = ref(false)
const loading = ref(false)
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await modulesApi.getChromeSync(props.moduleId)
    enabled.value = Boolean(data.enabled)
    emit('update:enabled', enabled.value)
    if (data.chrome_version != null) emit('version', Number(data.chrome_version))
  } finally {
    loading.value = false
  }
}

async function handleChange(value) {
  saving.value = true
  try {
    const data = await modulesApi.updateChromeSync(props.moduleId, { enabled: Boolean(value) })
    enabled.value = Boolean(data.enabled)
    emit('update:enabled', enabled.value)
    if (data.chrome_version != null) emit('version', Number(data.chrome_version))
  } catch {
    enabled.value = !value
    emit('update:enabled', enabled.value)
  } finally {
    saving.value = false
  }
}

watch(
  () => chrome.chromeMajorVersion,
  async () => {
    if (!enabled.value) return
    const detail = await modulesApi.get(props.moduleId)
    const value = detail?.params?.chrome_version
    if (value != null) emit('version', Number(value))
  },
)

onMounted(async () => {
  await chrome.load().catch(() => {})
  await load()
})
</script>

<style scoped>
.chrome-sync {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 12px;
  margin-bottom: 12px;
  border: 1px solid rgba(120, 130, 160, 0.18);
  border-radius: 10px;
  background: rgba(250, 251, 255, 0.7);
}
.chrome-sync-copy { display: flex; flex-direction: column; gap: 3px; }
.chrome-sync-copy strong { font-size: 13px; }
.chrome-sync-copy span { color: #7a8194; font-size: 12px; }
.chrome-sync.disabled { opacity: 0.72; }
</style>
