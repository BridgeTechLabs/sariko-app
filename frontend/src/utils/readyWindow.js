// Mirrors backend READY_WINDOW (backend/src/apis/sellers.py): marking ready books Lalamove right away,
// so a scheduled order may only go ready this long before its delivery_appointment.
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
