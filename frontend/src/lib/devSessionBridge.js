// DEV ONLY (imported from main.js only when VITE_DEV_PANEL=true, like the dev panel): the DEV admin's Test scenarios
// page signs this app in as the test buyer / seller inside its phone frame. It posts tokens it got from its own
// backend; the session is stored the usual way (supabase.auth.setSession), then the page reloads at the asked path
// so authStore.bootstrap loads the user, profile, cart and orders as on any start.
import { supabase } from '@/lib/supabase'
import { SESSION_MESSAGE, parseSessionMessage } from '@/lib/devSessionMessage'

export function listen() {
    window.addEventListener('message', async (event) => {
        const msg = parseSessionMessage(event.origin, event.data)
        if (!msg) return
        const { error } = await supabase.auth.setSession({ access_token: msg.access_token, refresh_token: msg.refresh_token })
        event.source?.postMessage({ type: `${SESSION_MESSAGE}-${error ? 'error' : 'ok'}` }, event.origin)
        if (!error) window.location.assign(msg.redirect)
    })
}
