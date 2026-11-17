// The buyer's refund chip from refund_state (T172): the same words on the order list and the order page (T178 A44).
// A failed refund shows as on its way: the team retries it.
export function refundChip(order) {
    const state = order?.refund_state
    if (state === 'refunded') return { key: 'order_detail.refund_processed', cls: 'refund-processed' }
    return state ? { key: 'order_detail.refund_pending', cls: 'refund-pending' } : null
}
