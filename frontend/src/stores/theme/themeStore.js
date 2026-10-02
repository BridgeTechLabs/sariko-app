import { defineStore } from 'pinia'
import {
    APP_THEME_KEY, THEME_MODES,
    applyTheme, readQueryTheme, readStoredTheme,
} from '@/utils/theme'

export const useThemeStore = defineStore('themeStore', {
    state: () => ({
        theme: 'dark', // 'light' | 'dark'
    }),

    getters: {
        isDarkMode: (state) => state.theme === 'dark',
    },

    actions: {
        init() {
            // ?theme_mode= is persisted, so it only needs to be passed once
            const fromQuery = readQueryTheme()
            if (fromQuery) this.setTheme(fromQuery)
            else this._apply(readStoredTheme())

            // Sync between tabs
            window.addEventListener('storage', (e) => {
                if (e.key === APP_THEME_KEY && THEME_MODES.includes(e.newValue)) this._apply(e.newValue)
            })
        },

        setTheme(mode) {
            if (!THEME_MODES.includes(mode)) return
            localStorage.setItem(APP_THEME_KEY, mode)
            this._apply(mode)
        },

        toggleTheme() {
            this.setTheme(this.isDarkMode ? 'light' : 'dark')
        },

        _apply(mode) {
            this.theme = mode
            applyTheme(mode)
        },
    },
})
