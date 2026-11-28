import { createApp } from 'vue'
import { createPinia } from 'pinia'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'
import 'element-plus/dist/index.css'
import '@/styles/global.css'
import App from './App.vue'
import router from './router'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.mount('#app')
