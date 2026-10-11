// While an order is 'ready', its list badge shows the live Lalamove step instead
// (order lists embed deliveries(status), see backend dao_orders list queries).
const LIVE_STEPS = ['ASSIGNING_DRIVER', 'ON_GOING', 'PICKED_UP']

// i18n key for the live delivery step, or null to fall back to the order status badge
export function liveDeliveryKey(order) {
    const step = order.status === 'ready' && order.deliveries?.[0]?.status
    return LIVE_STEPS.includes(step) ? `delivery_tracker.status_${step}` : null
}
