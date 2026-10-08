// Web Push handlers, pulled into the Workbox-generated sw.js via workbox.importScripts (vite.config.js).
// Payload from backend services/push_service.py: { title, body, url }

self.addEventListener('push', (event) => {
    const data = event.data ? event.data.json() : {}
    // iOS revokes the subscription if a push arrives without a visible notification — always show one.
    event.waitUntil(
        self.registration.showNotification(data.title || 'Sariko', {
            body: data.body,
            icon: '/icons/icon-192x192.png',
            data: { url: data.url || '/' },
        })
    )
})

self.addEventListener('notificationclick', (event) => {
    event.notification.close()
    const url = event.notification.data.url
    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
            const open = windows[0]
            if (open) return open.focus().then((client) => client.navigate(url))
            return self.clients.openWindow(url)
        })
    )
})
