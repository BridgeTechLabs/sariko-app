// Marking ready books Lalamove right away, so before this window opens the seller
// has to confirm (the driver may come well before the delivery_appointment).
export const READY_WINDOW_MINUTES = 45

// Minutes until a confirmed order may be marked ready; 0 = now (or no appointment).
export function minutesUntilReady(order, now = Date.now()) {
    if (order.status !== 'confirmed' || !order.delivery_appointment) return 0
    const opensAt = new Date(order.delivery_appointment).getTime() - READY_WINDOW_MINUTES * 60_000
    return Math.max(0, Math.ceil((opensAt - now) / 60_000))
}

// 80 → "1h 20m", 5 → "5m"
export function formatWait(minutes) {
    const h = Math.floor(minutes / 60)
    return h ? `${h}h ${minutes % 60}m` : `${minutes}m`
}

// Resolves true when it's time already, or the seller confirms booking the delivery early.
export function confirmEarlyReady(vm, order) {
    if (!minutesUntilReady(order)) return Promise.resolve(true)
    const appointment = new Date(order.delivery_appointment)
    const time = appointment.toLocaleString(vm.$i18n.locale === 'vi' ? 'vi-VN' : 'en-PH', {
        weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
        timeZone: 'Asia/Ho_Chi_Minh', hour12: false,
    })
    const wait = formatWait(Math.max(0, Math.ceil((appointment.getTime() - Date.now()) / 60_000)))
    return new Promise(resolve => {
        vm.$q.dialog({
            class: 'ready-early-dialog',
            title: vm.$t('seller_order_detail.ready_early_title'),
            message: vm.$t('seller_order_detail.ready_early_body', { time, wait }),
            ok: { label: vm.$t('seller_order_detail.ready_early_confirm'), unelevated: true, noCaps: true, class: 'ready-early-ok' },
            cancel: { label: vm.$t('common.button_label_cancel'), flat: true, noCaps: true },
            dark: true,
        }).onOk(() => resolve(true)).onCancel(() => resolve(false))
    })
}
