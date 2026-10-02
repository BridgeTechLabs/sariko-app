import { Dark } from 'quasar'

export const APP_THEME_KEY = 'app-theme'   // localStorage: 'light' | 'dark'
export const THEME_MODE_KEY = 'theme_mode' // query param override: ?theme_mode=light
export const THEME_MODES = ['light', 'dark']
// App is dark-first; most components still hardcode dark colors.
export const DEFAULT_THEME = 'dark'

export function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme)
    Dark.set(theme === 'dark') // keep Quasar components (q-dialog, q-menu...) in sync
}

export function readQueryTheme() {
    const fromQuery = new URLSearchParams(window.location.search).get(THEME_MODE_KEY)
    return THEME_MODES.includes(fromQuery) ? fromQuery : null
}

export function readStoredTheme() {
    // Old 'system' values fall back to DEFAULT_THEME
    const stored = localStorage.getItem(APP_THEME_KEY)
    return THEME_MODES.includes(stored) ? stored : DEFAULT_THEME
}
