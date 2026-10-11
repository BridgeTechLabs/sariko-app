import apiUsers from '@/apis/users/apiUsers'

// One subscription per device: buyer "Order updates" and seller "New order notifications"
// are the same switch. Backend decides who gets what (services/push_service.py).

function isPushSupported() {
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

// pushManager.subscribe wants the VAPID public key as bytes, not base64url
function urlBase64ToUint8Array(base64Url) {
    const base64 = (base64Url + '='.repeat((4 - base64Url.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/')
    return Uint8Array.from(atob(base64), (c) => c.charCodeAt(0))
}

export async function getPushSubscription() {
    if (!isPushSupported() || Notification.permission !== 'granted') return null
    const registration = await navigator.serviceWorker.getRegistration()
    return registration ? registration.pushManager.getSubscription() : null
}

// Call from a click handler — iOS only shows the permission prompt for a user gesture.
// Returns 'enabled' | 'unsupported' | 'blocked'
export async function enablePush() {
    if (!isPushSupported()) return 'unsupported'
    // No service worker in `npm run dev` (vite-plugin-pwa is build-only) and none in an iOS Safari tab
    const registration = await navigator.serviceWorker.getRegistration()
    if (!registration) return 'unsupported'

    const permission = await Notification.requestPermission()
    if (permission !== 'granted') return 'blocked'

    const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(import.meta.env.VITE_VAPID_PUBLIC_KEY),
    })
    await apiUsers.createPushSubscription(subscription.toJSON())
    return 'enabled'
}

// The push service then answers 410 for this endpoint and the backend drops the row.
export async function disablePush() {
    const subscription = await getPushSubscription()
    if (subscription) await subscription.unsubscribe()
}
