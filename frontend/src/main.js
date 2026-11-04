import { createApp } from 'vue'
import { registerSW } from 'virtual:pwa-register'
import VueAxios from 'vue-axios'
import axios from 'axios'
import App from './App.vue'
import '@/assets/quasar/main.scss'
import './assets/tokens.css'
import './assets/tokens-layout.css'
import './assets/main.css'
import './assets/v1-legacy.css' // V1 palette over the V2 tokens; remove when V2 replaces V1
import '@fontsource/open-sans/400.css'
import '@fontsource/open-sans/600.css'
import '@fontsource/open-sans/700.css'

const app = createApp(App)
app.use(VueAxios, axios);

window.$http = window.axios = axios;

const plugins = import.meta.glob('./plugins/*.js', { eager: true });
for (const path in plugins) {
    const plugin = plugins[path];
    plugin.default(app);
}

app.mount('#app')

// DEV ONLY: the DEV admin's Test scenarios phone frame signs this app in as a test account (lib/devSessionBridge.js).
// Vite inlines the flag at build time, so the prod bundle doesn't contain it.
if (import.meta.env.VITE_DEV_PANEL === 'true') import('@/lib/devSessionBridge.js').then((m) => m.listen())

// Service worker via vite-plugin-pwa (registerType 'autoUpdate'): when a deploy ships a new
// sw.js it takes over and the open page reloads, so nobody keeps running the old bundle.
// The /join draft is kept in localStorage, so that reload loses no typed form data.
registerSW({ immediate: true })
