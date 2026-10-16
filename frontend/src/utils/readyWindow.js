import { i18n } from '@/plugins/i18n'

// Marking ready books Lalamove right away, so before this window opens the seller
// has to confirm (the driver may come well before the delivery_appointment).
export const READY_WINDOW_MINUTES = 45

// Minutes until a confirmed order may be marked ready; 0 = now (or no appointment).
export function minutesUntilReady(order, now = Date.now()) {
    if (order.status !== 'confirmed' || !order.delivery_appointment) return 0
    const opensAt = new Date(order.delivery_appointment).getTime() - READY_WINDOW_MINUTES * 60_000
    return Math.max(0, Math.ceil((opensAt - now) / 60_000))
}

// 80 → "1 giờ 20 phút" / "1 hr 20 min", 5 → "5 phút" / "5 min" (current locale)
export function formatWait(minutes) {
    const t = i18n.global.t
    const h = Math.floor(minutes / 60)
    const m = minutes % 60
    if (!h) return t('common.duration_minutes', { m })
    return m ? t('common.duration_hours_minutes', { h, m }) : t('common.duration_hours', { h })
}

// Line under the Accept / Ready button, from the backend `deadline`: pending → when the order
// auto-cancels, confirmed → when the buyer may cancel for a refund. null = nothing to show
// (no deadline, or a scheduled order still showing "Ready in …").
export function deadlineHint(vm, order, now = Date.now()) {
    if (!order.deadline || minutesUntilReady(order, now)) return null
    const minutes = Math.ceil((new Date(order.deadline).getTime() - now) / 60_000)
    const pending = order.status === 'pending'
    if (minutes <= 0) {
        return { text: vm.$t(pending ? 'seller_home.deadline_auto_cancel_now' : 'seller_home.deadline_buyer_can_cancel'), urgent: true }
    }
    const key = pending ? 'seller_home.deadline_auto_cancel' : 'seller_home.deadline_buyer_cancel'
    return { text: vm.$t(key, { wait: formatWait(minutes) }), urgent: minutes <= 5 }
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
