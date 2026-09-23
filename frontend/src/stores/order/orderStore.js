import { defineStore } from "pinia";
import apiOrders from "@/apis/orders/apiOrders";
import { createPoller } from "@/composables/createPoller";

const ORDER_LIST_POLL_MS = 15_000
const ORDER_DETAIL_POLL_MS = 10_000

export const useOrderStore = defineStore("orderStore", {
    state() {
        return {
            orders: [],
            currentOrder: null,
            loading: false,
            selectedFilter: 'all',

            _ordersPoller: null,
            _ordersWatchers: 0,
            _orderDetailPoller: null,
            _orderDetailWatchedId: null,
        }
    },

    getters: {
        unpaidCount(state) {
            return state.orders.filter(
                o => o.payment_status === 'pending' && o.status !== 'cancelled'
            ).length
        }
    },

    actions: {
        async placeOrder(deliveryMethod, deliveryAddress, note, deliveryOpts = {}, deliveryAppointment = null) {
            try {
                this.loading = true
                const res = await apiOrders.createOrder(deliveryMethod, deliveryAddress, note, deliveryOpts, deliveryAppointment)
                if (res?.data?.success) {
                    this.currentOrder = res.data.order
                    return res.data.order
                }
                return null
            } catch (e) {
                console.error(`orderStore - placeOrder - ${e}`)
                throw e
            } finally {
                this.loading = false
            }
        },

        async getOrders({ silent = false } = {}) {
            try {
                if (!silent) this.loading = true
                const res = await apiOrders.getOrders()
                if (res?.data?.success) {
                    this.orders = res.data.orders
                }
            } catch (e) {
                console.error(`orderStore - getOrders - ${e}`)
            } finally {
                if (!silent) this.loading = false
            }
        },

        async getOrderDetail(orderId, { silent = false } = {}) {
            try {
                if (!silent) this.loading = true
                const res = await apiOrders.getOrderDetail(orderId)
                if (res?.data?.success) {
                    this.currentOrder = res.data.order
                }
            } catch (e) {
                console.error(`orderStore - getOrderDetail - ${e}`)
            } finally {
                if (!silent) this.loading = false
            }
        },

        async cancelOrder(orderId) {
            try {
                const res = await apiOrders.cancelOrder(orderId)
                if (res?.data?.success) {
                    if (this.currentOrder?.id === orderId) {
                        this.currentOrder.status = 'cancelled'
                    }
                    const idx = this.orders.findIndex(o => o.id === orderId)
                    if (idx !== -1) this.orders[idx].status = 'cancelled'
                }
            } catch (e) {
                console.error(`orderStore - cancelOrder - ${e}`)
                throw e
            }
        },

        // ─── Polling: buyer orders list (refcount) ─────────────────────────
        startWatchingOrders() {
            this._ordersWatchers += 1
            if (this._ordersPoller) return
            this._ordersPoller = createPoller({
                name: 'buyer-orders',
                intervalMs: ORDER_LIST_POLL_MS,
                fetch: () => this.getOrders({ silent: true }),
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

        // ─── Polling: buyer order detail (single page only) ────────────────
        startWatchingOrderDetail(orderId) {
            if (this._orderDetailPoller && this._orderDetailWatchedId !== orderId) {
                this._orderDetailPoller.stop()
                this._orderDetailPoller = null
            }
            if (this._orderDetailPoller) return

            this._orderDetailWatchedId = orderId
            this._orderDetailPoller = createPoller({
                name: `buyer-order-${orderId}`,
                intervalMs: ORDER_DETAIL_POLL_MS,
                fetch: () => this.getOrderDetail(orderId, { silent: true }),
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
    }
})
