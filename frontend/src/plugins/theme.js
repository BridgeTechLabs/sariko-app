import { useThemeStore } from '@/stores/theme/themeStore'

// Loaded after pinia.js / quasar.js (plugins are globbed alphabetically in main.js)
export default function useThemePlugin() {
    useThemeStore().init()
    console.log("Loaded Theme plugin")
}
