// No imports, so tests/frontend/orderStage.check.mjs runs it with plain node
// (vnTime.js pulls in the i18n plugin). Same Vietnam-day rule as vnTime.vnDay.
const vnDay = value => new Date(value).toLocaleDateString('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' })

// "2026-11-12": the Vietnam day the seller starts cooking a pre-order
// (delivery day − preorder_days from the backend), or null for a same-day order.
export function cookingDay(order) {
    if (!(order?.preorder_days > 0) || !order.delivery_appointment) return null
    const d = new Date(vnDay(order.delivery_appointment))   // midnight UTC of that day
    d.setUTCDate(d.getUTCDate() - order.preorder_days)
    return d.toISOString().slice(0, 10)
}

// A confirmed pre-order before its cooking day: the buyer sees "Scheduled" instead of "Preparing".
// Compared by Vietnam day, not hour; re-evaluated on every render / poll.
export function isScheduled(order, now = Date.now()) {
    const day = order?.status === 'confirmed' && cookingDay(order)
    return !!day && vnDay(now) < day
}
