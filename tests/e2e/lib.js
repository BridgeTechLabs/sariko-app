// Shared helpers: accounts from env, en-PH text by i18n key, sign-in, API calls, page health (E6).
import { readFileSync } from 'fs'
import { expect } from '@playwright/test'

const locales = (file) => JSON.parse(readFileSync(new URL(`../../frontend/src/i18n/locales/${file}`, import.meta.url), 'utf8'))
const TEXTS = { en_ph: locales('en-PH.json'), vi: locales('vi.json') }
let shown = 'en_ph'   // the language the app shows: a profile's preferred language wins over the sign-in pick
export const API_URL = process.env.API_URL || 'https://api-dev.sariko.store/rest/v1'

// The text the user sees for an i18n key in the language shown, params filled in ({name} -> value).
export function t(key, params = {}) {
    const text = key.split('.').reduce((o, k) => o?.[k], TEXTS[shown])
    if (typeof text !== 'string') throw new Error(`no ${shown} text for ${key}`)
    return text.replace(/\{(\w+)\}/g, (_, k) => params[k] ?? '')
}

export function account(who) {
    const email = process.env[`DEV_${who}_EMAIL`], password = process.env[`DEV_${who}_PASSWORD`]
    if (!email || !password) throw new Error(`set DEV_${who}_EMAIL / DEV_${who}_PASSWORD (values in .config/sariko/dummy_creds)`)
    return { email, password }
}

// Never on PROD: these tests write orders and carts.
export function refuseProd(url) {
    if (/(^|\/\/)(app|admin|api)\.sariko\.store/.test(url)) throw new Error(`refusing to run on PROD: ${url}`)
}

// Guests see English; a signed-in account sees its profile language (t() follows it, no profile is changed).
export async function guest(page) {
    await page.addInitScript(() => localStorage.getItem('lang') || localStorage.setItem('lang', 'en_ph'))
    shown = 'en_ph'
}

// Sign in to the app (the form fields are the email box and the password box).
export async function signIn(page, who) {
    const { email, password } = account(who)
    await guest(page)
    await page.goto('/signin')
    refuseProd(page.url())
    await page.locator('input[type="text"], input[type="email"]').first().fill(email)
    await page.locator('input[type="password"]').fill(password)
    await page.locator('input[type="password"]').press('Enter')
    await page.waitForURL((u) => !u.pathname.startsWith('/signin'), { timeout: 20_000 })
    await page.waitForLoadState('networkidle')
    shown = await page.evaluate(() => localStorage.getItem('lang')) || 'en_ph'
    TOKENS.set(page, await page.evaluate(() => {
        const key = Object.keys(localStorage).find((k) => k.startsWith('sb-') && k.endsWith('-auth-token'))
        return JSON.parse(localStorage.getItem(key)).access_token
    }))
}

// The signed-in user's Supabase access token, kept at sign-in: setup / clean-up through the API still work
// once the page has left the app (VNPay).
const TOKENS = new WeakMap()

export async function api(page, method, path, data) {
    const res = await page.request.fetch(API_URL + path, { method, data, headers: { Authorization: `Bearer ${TOKENS.get(page)}` } })
    return { status: res.status(), body: await res.json().catch(() => null) }
}

// E6: collect console errors and 5xx answers while the test runs; checkPage() asserts on the open page.
export function watch(page) {
    const problems = []
    // Cloudflare's analytics beacon is not the app (it is refused from localhost)
    page.on('console', (m) => m.type() === 'error' && !`${m.text()} ${m.location().url}`.includes('cloudflareinsights.com')
        && problems.push(`console: ${m.text()} ${m.location().url}`))
    page.on('response', (r) => r.status() >= 500 && problems.push(`${r.status()} ${r.request().method()} ${r.url()}`))
    return problems
}

const RAW_ICON = /\b(expand_less|expand_more|chevron_left|chevron_right|arrow_drop_down|arrow_back|keyboard_arrow_\w+|access_time|check_circle)\b/
// Every i18n key ("cart_page.note_label"...): one shown as text means a missing translation.
const KEYS = []
const walk = (o, path) => Object.entries(o).forEach(([k, v]) => typeof v === 'object' ? walk(v, `${path}${k}.`) : KEYS.push(path + k))
Object.values(TEXTS).forEach((texts) => walk(texts, ''))

export async function checkPage(page, problems, { noSideScroll = true } = {}) {
    await page.waitForLoadState('networkidle').catch(() => {})
    const text = await page.locator('body').innerText()
    expect(text, 'raw icon font name on the page').not.toMatch(RAW_ICON)
    expect(KEYS.filter((k) => text.includes(k)), 'raw i18n keys on the page').toEqual([])
    // A font icon whose font never loaded: no svg / img, no ligature text, no ::before glyph
    const blank = await page.$$eval('.q-icon', (els) => els.filter((e) => e.offsetParent && !e.querySelector('svg, img')
        && !e.textContent.trim() && ['none', 'normal', '""'].includes(getComputedStyle(e, '::before').content)
        && /\b(fa[srlbd]?|fa-[\w-]+|material-icons[\w-]*|mdi)\b/.test(e.className)).length)
    expect(blank, 'invisible Quasar icons').toBe(0)
    if (noSideScroll) {
        const wide = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
        expect(wide, 'page scrolls sideways').toBeLessThanOrEqual(1)
    }
    expect(problems, 'console errors / 5xx').toEqual([])
}
