// Build check (G16): a title, column or label is a short noun phrase, never a sentence ("Orders are late",
// "Refunded by hand"). Reads keys whose last part ends in title / heading / header / label / _col or starts with col_
// (sub-lines such as subtitle / hint / description are skipped) in en-PH.json and vi.json.
// Old offenders sit in title-check-allow.json ("<locale>:<key>"); the list only shrinks: an entry that now passes fails
// the build until it is removed. New titles must use such a key name so this check sees them.
// Known hole: Vietnamese does not conjugate, so a vi sentence without đã / đang / được / bị / sẽ / là
// ("Hôm nay bán", "Quán nhận đơn") passes; the vi text is read when the UI is approved.
import { readFileSync } from 'node:fs'

const IN_SCOPE = /(title|heading|header|label|_col)$|^col_/i
const SUB_LINE = /subtitle|placeholder|hint|desc|body|message|tooltip/i
const AUX = new Set(['is', 'are', 'was', 'were', 'be', 'been', 'has', 'have', 'had', 'will', 'can', 'cannot'])
const TO_OK = new Set(['the', 'a', 'an', 'your', 'home', 'cart', 'top']) // "to" + these is a place, not a verb
const BEFORE_ED = new Set(['a', 'an', 'the', 'new']) // "a finished order": the -ed word is an adjective
const NOT_ED = new Set(['need', 'speed', 'feed', 'seed', 'red', 'bed', 'hundred', 'shed', 'embed']) // nouns, not past tense
const VI_STATE = new Set(['đã', 'đang', 'được', 'bị', 'sẽ', 'là'])

function englishHit(text) {
    const w = text.match(/[A-Za-z'-]+/g) || [] // "Home-cooked" stays one word: a compound adjective, not past tense
    const lw = w.map((x) => x.toLowerCase())
    for (let i = 0; i < w.length; i++) {
        const t = lw[i]
        const next = lw[i + 1]
        if (AUX.has(t) || t.endsWith("n't")) return w[i]
        if ((t.endsWith('ed') || t === 'split') && next === 'by') return `${w[i]} by`
        if (t.endsWith('ing') && next === 'from') return `${w[i]} from`
        if (t === 'to' && next && /^[a-z]/.test(w[i + 1]) && !TO_OK.has(next)) return `to ${w[i + 1]}`
        if (i > 0 && t.endsWith('ed') && !BEFORE_ED.has(lw[i - 1]) && !NOT_ED.has(t)) return w[i]
    }
}

function vietnameseHit(text) {
    const w = text.toLowerCase().split(/[\s,.:;!?()"'/|–-]+/).filter(Boolean)
    // "chuẩn bị" (prepare) is one word, its "bị" is not the passive marker
    return w.length >= 4 ? w.find((t, i) => VI_STATE.has(t) && !(t === 'bị' && w[i - 1] === 'chuẩn')) : undefined
}

const allow = new Set(JSON.parse(readFileSync(new URL('./title-check-allow.json', import.meta.url), 'utf8')))
const allowed = allow.size
const bad = []
let checked = 0
for (const [locale, hit] of [['en-PH', englishHit], ['vi', vietnameseHit]]) {
    const walk = (node, prefix) => {
        for (const [k, v] of Object.entries(node)) {
            if (v && typeof v === 'object') walk(v, `${prefix}${k}.`)
            else if (typeof v === 'string' && IN_SCOPE.test(k) && !SUB_LINE.test(k)) {
                checked++
                const id = `${locale}:${prefix}${k}`
                const word = hit(v.replace(/\{[^}]*\}/g, ' '))
                if (!word || allow.delete(id)) continue
                bad.push(`${id} = "${v}"  (caught: "${word}")`)
            }
        }
    }
    walk(JSON.parse(readFileSync(new URL(`../src/i18n/locales/${locale}.json`, import.meta.url), 'utf8')), '')
}
// what is left in allow passes now or no longer exists
if (bad.length || allow.size) {
    for (const b of bad) console.error(b)
    for (const id of allow) console.error(`remove from allowlist: ${id}`)
    if (bad.length) console.error('Title = short noun phrase (G16); explanation goes in the sub-line')
    process.exit(1)
}
console.log(`titles: ok (${checked} checked, ${allowed} allowed)`)
