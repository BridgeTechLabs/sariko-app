<script>
import { useDashboardStore } from '@/stores/seller/dashboardStore';

// Jack 2026-10-20: ring every 10 s while any order waits for accept / reject, no cap.
// Not a business parameter (no admin_settings key on purpose).
const RING_EVERY_MS = 10_000
const UNLOCK_EVENTS = ['pointerdown', 'keydown', 'touchstart']

// Mounted once in App.vue for sellers, so the order poller and the new-order chime run
// on every page (Orders, Menu, Inbox, Me, chat...), not only on Today.
export default {
    name: 'SellerOrderAlert',

    computed: {
        pendingIds() {
            return useDashboardStore().orders.filter(o => o.status === 'pending').map(o => o.id)
        },
    },

    watch: {
        // A new pending order rings right away instead of waiting for the next 10 s tick.
        pendingIds(ids, oldIds) {
            if (ids.some(id => !oldIds.includes(id))) this.ring()
        },
    },

    async mounted() {
        this.audio = new Audio('/sounds/new-order.mp3')
        // Browsers only allow sound after a user gesture: prime the element on the first one.
        this.unlock = () => {
            this.audio.play().then(() => { this.audio.pause(); this.audio.currentTime = 0 }).catch(() => {})
            UNLOCK_EVENTS.forEach(e => window.removeEventListener(e, this.unlock))
        }
        UNLOCK_EVENTS.forEach(e => window.addEventListener(e, this.unlock))

        const store = useDashboardStore()
        if (!store.hasLoadedOrders) await store.fetchOrders({ silent: true })
        store.startWatchingOrders()
        this.timer = setInterval(() => { if (this.pendingIds.length) this.ring() }, RING_EVERY_MS)
    },

    beforeUnmount() {
        useDashboardStore().stopWatchingOrders()
        clearInterval(this.timer)
        UNLOCK_EVENTS.forEach(e => window.removeEventListener(e, this.unlock))
    },

    methods: {
        ring() {
            this.audio.currentTime = 0
            this.audio.play().catch(err => console.warn('SellerOrderAlert - ring -', err))
        },
    },

    render() {
        return null
    },
}
</script>
