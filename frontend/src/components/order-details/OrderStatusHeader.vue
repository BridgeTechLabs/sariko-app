<script>
import { CircleCheckBig, Clock, CircleX } from 'lucide-vue-next';
import { useOrderStore } from '@/stores/order/orderStore.js';
import { cookingDay, isScheduled } from '@/utils/orderStage';

// Cancels made by the system store a fixed English text (backend constants);
// show those translated. Reasons a seller picked or typed are shown as written.
const SYSTEM_REASON_KEYS = {
    'Seller did not confirm in time': 'order_detail.reason_seller_timeout',                      // services/order_expiry.py
    'Driver booking failed': 'order_detail.reason_no_driver',                                 // apis/sellers.py
    'Driver booking failed after 3 attempts': 'order_detail.reason_no_driver',                // same, orders before 2026-10-15
    'Delivery failed': 'order_detail.reason_delivery_failed',                                 // apis/orders.py (T177 A13)
    'Seller was late': 'order_detail.reason_seller_late',                                     // apis/orders.py
    'Sold out': 'order_detail.reason_sold_out',                                               // dao/dao_orders.py
}

export default {
    components: {
        CircleCheckBig, Clock, CircleX
    },

    computed: {
        order() {
            return useOrderStore().currentOrder
        },
        isPaymentPending() {
            return this.order?.payment_status === 'pending' && this.order?.status === 'pending'
        },
        isPending() {
            return this.order?.status === 'pending'
        },
        isCancelled() {
            return this.order?.status === 'cancelled'
        },
        isDeliveryFailed() {
            return this.order?.status === 'delivery_failed'
        },
        statusTitle() {
            if (this.isPaymentPending) return this.$t('order_detail.status_title_awaiting_payment')
            if (isScheduled(this.order)) return this.$t('order_detail.status_title_scheduled')
            const map = {
                pending: 'status_title_pending',
                confirmed: 'status_title_confirmed',
                ready: 'status_title_ready',
                done: 'status_title_done',
                cancelled: 'status_title_cancelled',
                delivery_failed: 'status_title_delivery_failed',
            }
            const key = map[this.order?.status]
            return key ? this.$t(`order_detail.${key}`) : this.$t('order_detail.title')
        },
        cancellationReason() {
            const reason = this.order?.cancellation_reason
            if (!reason) return null
            return SYSTEM_REASON_KEYS[reason] ? this.$t(SYSTEM_REASON_KEYS[reason]) : reason
        },
        statusSubtext() {
            if (this.isPaymentPending) return this.$t('order_detail.status_subtext_awaiting_payment')
            if (isScheduled(this.order)) {
                const date = new Date(`${cookingDay(this.order)}T12:00:00+07:00`).toLocaleDateString(
                    this.$i18n.locale === 'vi' ? 'vi-VN' : 'en-GB',
                    { weekday: 'short', day: '2-digit', month: '2-digit', timeZone: 'Asia/Ho_Chi_Minh' })
                return this.$t('order_detail.status_subtext_scheduled', { date })
            }
            if (this.isCancelled && this.cancellationReason) {
                return `${this.$t('order_detail.cancelled_reason')}: ${this.cancellationReason}`
            }
            const map = {
                pending: 'status_subtext_pending',
                confirmed: 'status_subtext_confirmed',
                ready: this.order?.delivery_method === 'delivery'
                    ? 'delivery_tracker.status_subtext_ready'
                    : 'order_detail.status_subtext_ready_pickup',
                done: 'status_subtext_done',
                cancelled: 'status_subtext_cancelled',
                delivery_failed: 'status_subtext_delivery_failed',
            }
            const key = map[this.order?.status]
            if (!key) return ''
            if (this.order?.status === 'ready') return this.$t(key)
            return this.$t(`order_detail.${key}`)
        },
        statusIconColor() {
            if (this.isPaymentPending) return '#f97316'
            const map = {
                pending: '#f59e0b',
                confirmed: '#3b82f6',
                ready: '#10b981',
                done: '#10b981',
                cancelled: '#ef4444',
                delivery_failed: '#f59e0b',
            }
            return map[this.order?.status] || '#ffffff'
        },
        // refund_state (backend, T172). A failed refund shows as in progress: the team retries it.
        refundChip() {
            const pending = { label: this.$t('order_detail.refund_pending'), cls: 'refund-pending' }
            const map = {
                in_progress: pending,
                failed: pending,
                refunded: { label: this.$t('order_detail.refund_processed'), cls: 'refund-processed' },
            }
            return map[this.order?.refund_state] || null
        }
    }
}
</script>

<template>
    <div v-if="order" class="status-header">
        <div class="status-icon">
            <CircleX v-if="isCancelled" :size="64" :color="statusIconColor" />
            <Clock v-else-if="isPending || isDeliveryFailed" :size="64" :color="statusIconColor" />
            <CircleCheckBig v-else :size="64" :color="statusIconColor" />
        </div>
        <div class="status-title">{{ statusTitle }}</div>
        <div class="status-subtext">{{ statusSubtext }}</div>

        <div v-if="refundChip" class="refund-chip" :class="refundChip.cls">
            {{ refundChip.label }}
        </div>
    </div>

    <div v-else class="loading-state">
        <q-spinner color="amber" size="40px" />
    </div>
</template>

<style lang="scss" scoped>
.status-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: 20px;
}

.status-icon {
    margin-bottom: 16px;
}

.status-title {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 8px;
}

.status-subtext {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.5);
    text-align: center;
    line-height: 1.5;
}

.refund-chip {
    margin-top: 14px;
    padding: 5px 14px;
    border-radius: 100px;
    font-size: 12px;
    font-weight: 600;
}

.refund-pending   { background: rgba(245, 166, 35, 0.12); color: #f5a623; }
.refund-processed { background: rgba(34, 197, 94, 0.12);  color: #22c55e; }

.loading-state {
    display: flex;
    justify-content: center;
    padding-top: 100px;
}
</style>
