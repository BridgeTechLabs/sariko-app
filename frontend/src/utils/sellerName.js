// Seller name rules, the same as backend core/seller_kyc.py (docs/dev/seller-full-name N2, N6).
// The backend decides; this only warns early. tests/backend/unit/test_seller_name_rule.py runs the
// shared cases (seller_name_cases.json) through this file and the backend.

// Python's str.split() whitespace, so both sides squash the same characters.
const WS = /[\t\n\v\f\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/g

export function squash(text) {
    return (text || '').replace(WS, ' ').trim()
}

// "Nguyễn Văn Ân" -> "nguyen van an": bank holder names are written without accents.
function plain(text) {
    return squash(text).replace(/đ/g, 'd').replace(/Đ/g, 'D').normalize('NFD').replace(/\p{Mn}/gu, '').toLowerCase()
}

// Phone keyboards type curly quotes / long dashes: count them as ' and -
function punct(text) {
    return (text || '').replace(/[’ʼ‘]/g, "'").replace(/[–—]/g, '-')
}

// The full name to store, or null: letters, spaces and - ' . only (one word is fine).
export function cleanFullName(text) {
    const name = punct(squash(text).normalize('NFC'))
    return /^[\p{L}\p{M} '.-]*$/u.test(name) && /\p{L}/u.test(name) ? name : null
}

function words(text, ignoreAccents) {
    const t = punct(text).replace(/-/g, ' ').replace(/['.]/g, '')
    return (ignoreAccents ? plain(t) : squash(t).normalize('NFC').toLowerCase()).split(' ').filter(Boolean).sort()
}

// Same words as the full name, any order, each as many times; case and - ' . ignored, accents too
// for a bank holder (Luật TMĐT 122/2025 Đ21.2.b: the payout account is in the seller's own name).
export function nameMatches(typed, fullName, ignoreAccents = false) {
    const want = words(fullName, ignoreAccents).join(' ')
    return want !== '' && words(typed, ignoreAccents).join(' ') === want
}
