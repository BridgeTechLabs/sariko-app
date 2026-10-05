import { getCountries, getCountryCallingCode } from 'libphonenumber-js/min'

// flag-icons 4x3 SVGs as URLs (no-inline keeps tiny flags out of the JS bundle).
// Emitted to assets/flags/ and excluded from the PWA precache — see vite.config.js.
const FLAG_DIR = '/node_modules/flag-icons/flags/4x3/'
const FLAG_URLS = import.meta.glob('/node_modules/flag-icons/flags/4x3/*.svg', {
    query: '?no-inline',
    import: 'default',
    eager: true,
})

export const flagUrl = (iso) => FLAG_URLS[`${FLAG_DIR}${iso.toLowerCase()}.svg`] || null

export const dialCodeOf = (iso) => `+${getCountryCallingCode(iso)}`

// Country names come from Intl in the app language (i18n 'vi' / 'en_ph'), so no translation keys per country
export const getPhoneCountries = (appLocale) => {
    const locale = appLocale === 'vi' ? 'vi' : 'en'
    const names = new Intl.DisplayNames([locale], { type: 'region' })
    return getCountries()
        .map(iso => ({
            iso,
            name: names.of(iso),
            dialCode: dialCodeOf(iso),
            flag: flagUrl(iso),
        }))
        .sort((a, b) => a.name.localeCompare(b.name, locale))
}
