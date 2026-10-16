<script>
import { useJoinStore } from '@/stores/join/joinStore'

const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
let scriptPromise = null

function loadScript() {
    if (window.turnstile) return Promise.resolve()
    if (!scriptPromise) {
        scriptPromise = new Promise((resolve, reject) => {
            const s = document.createElement('script')
            s.src = SCRIPT_SRC
            s.async = true
            s.onload = resolve
            s.onerror = () => { scriptPromise = null; reject(new Error('turnstile script')) }
            document.head.appendChild(s)
        })
    }
    return scriptPromise
}

// Cloudflare Turnstile, loaded only on the last step. The token lands in the store.
export default {
    data() {
        return { failed: false, siteKey: import.meta.env.VITE_TURNSTILE_SITE_KEY }
    },

    computed: {
        store() {
            return useJoinStore()
        },
    },

    async mounted() {
        if (!this.siteKey) {
            this.failed = true
            return
        }
        try {
            await loadScript()
        } catch {
            this.failed = true
            return
        }
        if (this.unmounted) return
        this.store.turnstileWidgetId = window.turnstile.render(this.$refs.box, {
            sitekey: this.siteKey,
            theme: 'dark',
            callback: (token) => { this.store.turnstileToken = token },
            'expired-callback': () => { this.store.turnstileToken = null },
            'error-callback': () => { this.store.turnstileToken = null },
        })
    },

    beforeUnmount() {
        this.unmounted = true
        try {
            if (window.turnstile && this.store.turnstileWidgetId !== null) window.turnstile.remove(this.store.turnstileWidgetId)
        } catch { /* already gone */ }
        this.store.turnstileWidgetId = null
        this.store.turnstileToken = null
    },
}
</script>

<template>
    <div>
        <div ref="box" />
        <div v-if="failed" class="join-error">{{ $t('join_page.error_captcha_load') }}</div>
    </div>
</template>
