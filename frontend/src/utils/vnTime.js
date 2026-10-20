import { i18n } from '@/plugins/i18n'

const TZ = 'Asia/Ho_Chi_Minh'

// orders.created_at / deliveries.created_at are `timestamp without time zone` holding UTC:
// without a "Z" the browser reads them as local time (7 hours off in Vietnam).
export function parseDbTime(value) {
    if (!value) return null
    return new Date(/(Z|[+-]\d\d:?\d\d)$/.test(value) ? value : value + 'Z')
}

// Date / time in Vietnam time, in the current UI language.
export function formatVnTime(value, options) {
    const d = value instanceof Date ? value : parseDbTime(value)
    if (!d) return ''
    return d.toLocaleString(i18n.global.locale === 'vi' ? 'vi-VN' : 'en-PH', { timeZone: TZ, hour12: false, ...options })
}

// "2026-10-19": the Vietnam calendar day of a moment, for Today / Yesterday grouping.
export function vnDay(value) {
    const d = value instanceof Date ? value : parseDbTime(value)
    return d.toLocaleDateString('en-CA', { timeZone: TZ })
}
