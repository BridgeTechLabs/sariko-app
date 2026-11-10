import { defineStore } from "pinia";
import { createPoller } from "@/composables/createPoller";
import apiDeliveries from "@/apis/deliveries/apiDeliveries";

const DELIVERY_TERMINAL = ['COMPLETED', 'CANCELED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'LOST']
const DELIVERY_POLL_MS = 10_000

export const useDeliveryStore = defineStore("deliveryStore", {
    state() {
        return {
            quotation: null,
            currentDelivery: null,
            quotationLoading: false,
            _poller: null,
            _watchedOrderId: null,
        }
    },

    getters: {
        deliveryFee(state) {
            return state.quotation?.total_fee || 0
        },
        deliveryFeeText(state) {
            if (!state.quotation) return '--'
            return new Intl.NumberFormat('vi-VN').format(state.quotation.total_fee) + ' ₫'
        },
        isDeliveryActive(state) {
            const s = state.currentDelivery?.status
            return s && s !== 'COMPLETED' && !['CANCELED', 'REJECTED', 'EXPIRED', 'LOST'].includes(s)
        },
    },

    actions: {
        async getQuotation(sellerId, deliveryLat, deliveryLon, deliveryAddress) {
            this.quotationLoading = true
            this.quotation = null
            try {
                const res = await apiDeliveries.getQuotation(sellerId, deliveryLat, deliveryLon, deliveryAddress)
                if (res?.success) {
                    this.quotation = {
                        quotation_id: res.quotation_id,
                        total_fee: res.total_fee,
                        currency: res.currency,
                        distance_km: res.distance_km,
                    }
                }
            } catch (e) {
                console.error('deliveryStore - getQuotation -', e)
            } finally {
                this.quotationLoading = false
            }
        },

        async _fetchDelivery(orderId) {
            try {
                const res = await apiDeliveries.getDeliveryStatus(orderId)
                if (res?.success && res.delivery) {
                    this.currentDelivery = res.delivery
                }
            } catch (e) {
                console.error('deliveryStore - fetchDelivery -', e)
            }
        },

        async startWatching(orderId) {
            this.stopWatching()
            this._watchedOrderId = orderId

            await this._fetchDelivery(orderId)

            this._poller = createPoller({
                name: `delivery-${orderId}`,
                intervalMs: DELIVERY_POLL_MS,
                fetch: async () => {
                    if (DELIVERY_TERMINAL.includes(this.currentDelivery?.status)) {
                        // Terminal state — no need to keep polling
                        this.stopWatching()
                        return
                    }
                    await this._fetchDelivery(orderId)
                },
            })
            this._poller.start()
        },

        stopWatching() {
            if (this._poller) {
                this._poller.stop()
                this._poller = null
            }
            this._watchedOrderId = null
        },

        reset() {
            this.stopWatching()
            this.quotation = null
            this.currentDelivery = null
            this.quotationLoading = false
        },
    }
})
