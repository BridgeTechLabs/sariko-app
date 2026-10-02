<script>
import { useOrderStore } from '@/stores/order/orderStore.js';

export default {
    computed: {
        order() {
            return useOrderStore().currentOrder
        },
        subtotal() {
            if (!this.order) return 0
            return (this.order.total_amount || 0) - (this.order.delivery_fee || 0)
        },
        totalText() {
            if (!this.order) return ''
            return new Intl.NumberFormat('vi-VN').format(this.order.total_amount) + ' ₫'
        },
        statusLabel() {
            const map = {
                pending: 'status_pending',
                confirmed: 'status_confirmed',
                ready: 'status_ready',
                done: 'status_done',
                cancelled: 'status_cancelled',
            }
            const key = map[this.order?.status]
            return key ? this.$t(`order_detail.${key}`) : this.order?.status
        },
        statusColor() {
            if (this.order?.payment_status === 'pending' && this.order?.status !== 'cancelled') return 'orange'
            const map = {
                pending: 'amber',
                confirmed: 'info',
                ready: 'positive',
                done: 'positive',
                cancelled: 'negative',
            }
            return map[this.order?.status] || 'grey'
        }
    },

    methods: {
        formatPrice(value) {
            return new Intl.NumberFormat('vi-VN').format(value) + ' ₫'
        },
        formatAppointment(isoStr) {
            if (!isoStr) return ''
            const d = new Date(isoStr)
            return d.toLocaleString('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
        }
    }
}
</script>

<template>
    <div v-if="order" class="order-card">
        <div class="order-row">
            <span class="label">{{ $t('order_detail.label_status') }}</span>
            <q-badge :color="statusColor" text-color="black">
                {{ statusLabel }}
            </q-badge>
        </div>
        <div class="order-row">
            <span class="label">{{ $t('order_detail.label_seller') }}</span>
            <span>{{ order.seller_profiles?.store_name }}</span>
        </div>
        <div class="order-row">
            <span class="label">{{ $t('order_detail.label_delivery') }}</span>
            <span>{{ order.delivery_method === 'delivery' ? $t('order_detail.delivery_method_delivery') : $t('order_detail.delivery_method_pickup') }}</span>
        </div>
        <div class="order-row" v-if="order.delivery_address">
            <span class="label">{{ $t('order_detail.label_address') }}</span>
            <span class="address-text">{{ order.delivery_address }}</span>
        </div>
        <div class="order-row" v-if="order.delivery_appointment">
            <span class="label">{{ $t('order_detail.label_appointment') }}</span>
            <span class="appointment-text">{{ formatAppointment(order.delivery_appointment) }}</span>
        </div>
        <div class="order-row" v-if="order.note">
            <span class="label">{{ $t('order_detail.label_note') }}</span>
            <span>{{ order.note }}</span>
        </div>

        <div class="dashed-line" />

        <div class="order-row" v-for="item in order.order_items" :key="item.id">
            <span>{{ item.quantity }}x {{ item.name_snapshot }}<span v-if="item.variant_name_snapshot" class="order-variant"> ({{ item.variant_name_snapshot }})</span></span>
            <span>{{ formatPrice(item.price_snapshot * item.quantity) }}</span>
        </div>

        <div class="dashed-line" />

        <div class="order-row">
            <span class="label">{{ $t('order_detail.label_subtotal') }}</span>
            <span>{{ formatPrice(subtotal) }}</span>
        </div>
        <div class="order-row" v-if="order.delivery_fee">
            <span class="label">{{ $t('order_detail.label_delivery_fee') }}</span>
            <span>{{ formatPrice(order.delivery_fee) }}</span>
        </div>
        <div class="order-row total">
            <span>{{ $t('order_detail.label_total') }}</span>
            <span>{{ totalText }}</span>
        </div>
    </div>
</template>

<style lang="scss" scoped>
.order-card {
    width: 100%;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 20px;
}

.order-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 6px 0;
    font-size: 14px;

    &.total {
        font-weight: 700;
        font-size: 16px;
    }
}

.label {
    color: rgba(255, 255, 255, 0.5);
    font-weight: 500;
}

.address-text {
    text-align: right;
    max-width: 60%;
}

.appointment-text {
    font-weight: 600;
    color: var(--text-active);
}

.dashed-line {
    height: 1px;
    background: repeating-linear-gradient(
        to right, #454545 0px, #454545 10px, transparent 2px, transparent 15px
    );
    margin: 12px 0;
}

.order-variant {
    color: #f5A623;
    font-weight: 600;
}
</style>
