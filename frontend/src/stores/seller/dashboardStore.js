import { defineStore } from "pinia";
import apiSellerDashboard from "@/apis/sellers/apiSellerDashboard";
import apiDeliveries from "@/apis/deliveries/apiDeliveries";
import { createPoller } from "@/composables/createPoller";

const ORDER_LIST_POLL_MS = 10_000
const ORDER_DETAIL_POLL_MS = 10_000
const ORDER_TERMINAL = ['done', 'cancelled']

export const useDashboardStore = defineStore("dashboardStore", {
    state() {
        return {
            sellerId: null,
            sellerInfo: null,
            orders: [],
            orderDetails: null,
            orderDelivery: null,
            deliveryStatuses: {},
            isLoading: false,
            hasLoadedOrders: false,
            orderDetailLoading: false,
            selectedFilter: 'new',

            _ordersPoller: null,
            _ordersWatchers: 0,
            _orderDetailPoller: null,
            _orderDetailWatchedId: null,
        }
    },

    getters: {
        totalOrders(state) {
            return state.orders.length
        },
        revenue(state) {
            const value = state.orders
                .filter(o => o.status !== 'cancelled')
                .reduce((sum, o) => sum + (o.total_amount || 0), 0)
            if (!value) return '—'
            return new Intl.NumberFormat('vi-VN').format(value) + ' ₫'
        },
        pendingOrders(state) {
            return state.orders.filter(o => o.status === 'pending').length
        },
        recentOrders(state) {
            return state.orders.slice(0, 20)
        },
        actionDisplayCount(state) {
            return state.orders.filter(order =>
                ['pending', 'confirmed', 'delivery_failed'].includes(order.status)
            ).length
        },

        filteredOrders(state) {
            const filter = state.selectedFilter
            if (filter === 'all') return state.orders
            if (filter === 'new') return state.orders.filter(o => o.status === 'pending')
            if (filter === 'preparing') return state.orders.filter(o => o.status === 'confirmed')
            if (filter === 'ready') return state.orders.filter(o => o.status === 'ready')
            if (filter === 'completed') return state.orders.filter(o => o.status === 'done')
            if (filter === 'cancelled') return state.orders.filter(o => o.status === 'cancelled')
            return state.orders
        },
    },

    actions: {

        async fetchSellerInfo() {
            try {
                const res = await apiSellerDashboard.getSellerInfo()
                this.sellerId = res.seller_id
                this.sellerInfo = {
                    slug: res.slug,
                    store_name: res.store_name,
                    address: res.address,
                    phone: res.phone,
                    has_address: res.has_address,
                    has_phone: res.has_phone,
                }
            } catch (e) {
                console.error('dashboardStore - fetchSellerInfo -', e)
            }
        },

        async fetchOrders({ silent = false } = {}) {
            if (this.isLoading) return
            if (!silent) this.isLoading = true
            try {
                const res = await apiSellerDashboard.getOrders()
                this.orders = res.orders || []
            } catch (e) {
                console.error('dashboardStore - fetchOrders -', e)
            } finally {
                if (!silent) this.isLoading = false
                this.hasLoadedOrders = true
            }
        },

        async loadOrderDetail(orderId) {
            this.orderDetailLoading = true
            try {
                const res = await apiSellerDashboard.getOrderDetail(orderId)
                this.orderDetails = res.order || null
                if (this.orderDetails?.delivery_method === 'delivery'
                    && ['ready', 'done'].includes(this.orderDetails?.status)) {
                    await this._fetchDelivery(orderId)
                }
            } catch (e) {
                console.error('dashboardStore - loadOrderDetail -', e)
            } finally {
                this.orderDetailLoading = false
            }
        },

        async _fetchDelivery(orderId) {
            try {
                const res = await apiDeliveries.getSellerDeliveryStatus(orderId)
                this.orderDelivery = res?.delivery || null
            } catch (e) {
                console.error('dashboardStore - _fetchDelivery -', e)
            }
        },

        async refreshOrderDetailSilent(orderId) {
            try {
                const res = await apiSellerDashboard.getOrderDetail(orderId)
                this.orderDetails = res.order || null
            } catch (e) {
                console.error('dashboardStore - refreshOrderDetailSilent -', e)
            }
        },

        async refreshDeliverySilent(orderId) {
            try {
                const res = await apiDeliveries.getSellerDeliveryStatus(orderId)
                this.orderDelivery = res?.delivery || null
            } catch (e) {
                console.error('dashboardStore - refreshDeliverySilent -', e)
            }
        },

        // ─── Polling: seller orders list (refcount) ────────────────────────
        startWatchingOrders() {
            this._ordersWatchers += 1
            if (this._ordersPoller) return
            this._ordersPoller = createPoller({
                name: 'seller-orders',
                intervalMs: ORDER_LIST_POLL_MS,
                fetch: () => this.fetchOrders({ silent: true }),
            })
            this._ordersPoller.start()
        },

        stopWatchingOrders() {
            this._ordersWatchers = Math.max(0, this._ordersWatchers - 1)
            if (this._ordersWatchers === 0 && this._ordersPoller) {
                this._ordersPoller.stop()
                this._ordersPoller = null
            }
        },

        // ─── Polling: seller order detail + delivery (single page only) ────
        startWatchingOrderDetail(orderId) {
            // Switching to a different order: tear down previous poller
            if (this._orderDetailPoller && this._orderDetailWatchedId !== orderId) {
                this._orderDetailPoller.stop()
                this._orderDetailPoller = null
            }
            if (this._orderDetailPoller) return

            // Order already finished before the page opened — nothing left to watch
            if (this.orderDetails?.id === orderId && ORDER_TERMINAL.includes(this.orderDetails.status)) return

            this._orderDetailWatchedId = orderId
            this._orderDetailPoller = createPoller({
                name: `seller-order-detail-${orderId}`,
                intervalMs: ORDER_DETAIL_POLL_MS,
                fetch: async () => {
                    const prevStatus = this.orderDetails?.status
                    await this.refreshOrderDetailSilent(orderId)
                    const status = this.orderDetails?.status
                    const isDelivery = this.orderDetails?.delivery_method === 'delivery'
                    // The COMPLETED webhook sets deliveries.status and orders.status='done' together,
                    // so we must still fetch the delivery on the tick the order turns terminal —
                    // otherwise the final delivery step never leaves PICKED_UP.
                    const justBecameTerminal = ORDER_TERMINAL.includes(status) && !ORDER_TERMINAL.includes(prevStatus)
                    if (isDelivery && status && (!ORDER_TERMINAL.includes(status) || justBecameTerminal)) {
                        await this.refreshDeliverySilent(orderId)
                    }
                    // Terminal order can't change again — stop polling
                    if (ORDER_TERMINAL.includes(status)) this.stopWatchingOrderDetail()
                },
            })
            this._orderDetailPoller.start()
        },

        stopWatchingOrderDetail() {
            if (this._orderDetailPoller) {
                this._orderDetailPoller.stop()
                this._orderDetailPoller = null
                this._orderDetailWatchedId = null
            }
        },

        clearOrderDetail() {
            this.orderDetails = null
            this.orderDelivery = null
        },

        async setOrderStatus(orderId, newStatus, reason = null) {
            await apiSellerDashboard.updateOrderStatus(orderId, newStatus, reason)
            if (this.orderDetails?.id === orderId) {
                this.orderDetails.status = newStatus
                if (reason) this.orderDetails.cancellation_reason = reason
            }
            this.updateOrderLocally(orderId, newStatus)
        },

        async doRebookDelivery(orderId) {
            await apiDeliveries.rebookDelivery(orderId)
            await this._fetchDelivery(orderId)
            this.updateOrderLocally(orderId, 'ready')
            if (this.orderDetails?.id === orderId) this.orderDetails.status = 'ready'
        },

        async fetchDeliveryStatus(orderId) {
            this.deliveryStatuses = { ...this.deliveryStatuses, [orderId]: 'loading' }
            try {
                const res = await apiDeliveries.getSellerDeliveryStatus(orderId)
                this.deliveryStatuses = { ...this.deliveryStatuses, [orderId]: res.delivery }
            } catch (e) {
                this.deliveryStatuses = { ...this.deliveryStatuses, [orderId]: 'error' }
            }
        },

        setDeliveryStatus(orderId, statusObj) {
            this.deliveryStatuses = { ...this.deliveryStatuses, [orderId]: statusObj }
        },

        updateOrderLocally(orderId, newStatus) {
            const order = this.orders.find(o => o.id === orderId)
            if (order) order.status = newStatus
        },
    }
})
