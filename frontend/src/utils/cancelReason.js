// orders.cancellation_reason is a code (T178), shown in the viewer's language: i18n cancel_reason.<viewer>.<code>.
// Rows from before T178 hold an English sentence: the known ones map to their code, any other text shows as written.
// viewer: 'buyer' | 'seller'. Only the seller sees cancellation_note (a seller's "other" text); the buyer's API never sends it.
const LEGACY = {
    'Seller did not confirm in time': 'seller_timeout',
    'Driver booking failed': 'no_driver',
    'Driver booking failed after 3 attempts': 'no_driver',
    'Delivery failed': 'delivery_failed',
    'Seller was late': 'seller_late',
    'Sold out': 'sold_out',
}

export function cancelReasonText(vm, order, viewer) {
    const raw = order?.cancellation_reason
    if (!raw) return null
    const key = `cancel_reason.${viewer}.${LEGACY[raw] || raw}`
    return vm.$te(key) ? vm.$t(key, { note: order.cancellation_note || '' }) : raw
}
