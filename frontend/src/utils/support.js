// Seller support channel (email only, Jack 2026-10-20). Kept out of the locale files:
// a raw "@" there breaks vue-i18n, so messages take it as the {email} param.
export const SUPPORT_EMAIL = 'support' + '@' + 'sariko.store'
export const SUPPORT_MAILTO = `mailto:${SUPPORT_EMAIL}?subject=Sariko%20Seller%20Support`
