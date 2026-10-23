// DEV ONLY (used by lib/devSessionBridge.js, which loads only when VITE_DEV_PANEL=true): checks a sign-in message
// from the DEV admin's Test scenarios phone frame. Pure, so scripts/test-dev-session.mjs can test it.
export const SESSION_MESSAGE = 'sariko-dev-session'
const ADMIN_ORIGIN = /^(https:\/\/admin-dev\.sariko\.store|http:\/\/localhost:\d+)$/

// { access_token, refresh_token, redirect } for a valid message from the admin, else null.
export function parseSessionMessage(origin, data) {
    if (!ADMIN_ORIGIN.test(origin)) return null
    if (!data || data.type !== SESSION_MESSAGE) return null
    if (typeof data.access_token !== 'string' || !data.access_token || typeof data.refresh_token !== 'string' || !data.refresh_token) return null
    // only a path of this app: no other site, no protocol-relative //host
    const redirect = typeof data.redirect === 'string' && data.redirect.startsWith('/') && !data.redirect.startsWith('//') ? data.redirect : '/'
    return { access_token: data.access_token, refresh_token: data.refresh_token, redirect }
}
