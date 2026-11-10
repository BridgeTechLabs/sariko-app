// While an order is 'ready', its list badge shows the live delivery step instead
// (order lists carry delivery_status = the current trip's, backend dao_orders.with_current_trip, T180 A26).
const LIVE_STEPS = ['ASSIGNING_DRIVER', 'ON_GOING', 'PICKED_UP']

// Trip statuses after which nothing moves (both spellings of cancelled; LOST: after pickup, T177)
export const DELIVERY_TERMINAL = ['COMPLETED', 'CANCELED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'LOST']

export const isTripActive = (status) => !!status && !DELIVERY_TERMINAL.includes(status)

// i18n key for the live delivery step, or null to fall back to the order status badge
export function liveDeliveryKey(order) {
    const step = order.status === 'ready' && order.delivery_status
    return LIVE_STEPS.includes(step) ? `delivery_tracker.status_${step}` : null
}
