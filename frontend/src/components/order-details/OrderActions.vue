<script>
import { CreditCard } from 'lucide-vue-next';
import { useOrderStore } from '@/stores/order/orderStore.js';
import apiPayments from '@/apis/payments/apiPayments.js';
import { formatVnTime, vnDay } from '@/utils/vnTime';

export default {
    components: {
        CreditCard
    },

    data() {
        return {
            payingNow: false,
            cancelling: false,
            showCancelDialog: false,
            now: Date.now(),
        }
    },

    computed: {
        orderStore() {
            return useOrderStore()
        },
        order() {
            return this.orderStore.currentOrder
        },
        isPending() {
            return this.order?.status === 'pending'
        },
        isCancelled() {
            return this.order?.status === 'cancelled'
        },
        isPaymentPending() {
            return this.order?.payment_status === 'pending' && this.order?.status === 'pending'
        },
        totalText() {
            if (!this.order) return ''
            return new Intl.NumberFormat('vi-VN').format(this.order.total_amount) + ' ₫'
        },
        // Late confirmed / delivery_failed order: buyer may cancel + full refund from this time (backend cancel_after)
        lateCancelAt() {
            return this.order?.cancel_after ? new Date(this.order.cancel_after) : null
        },
        canLateCancel() {
            return !!this.lateCancelAt && this.now >= this.lateCancelAt.getTime()
        },
        // Pending order with a delivery time: cancel only until this time (backend cancel_before, T129)
        cancelBefore() {
            return this.order?.cancel_before ? new Date(this.order.cancel_before) : null
        },
        canCancelPending() {
            return this.isPending && (!this.cancelBefore || this.now <= this.cancelBefore.getTime())
        },
        hasActions() {
            return this.isPaymentPending || this.canCancelPending || !!this.lateCancelAt
        }
    },

    mounted() {
        this._clock = setInterval(() => { this.now = Date.now() }, 30_000)
    },

    beforeUnmount() {
        clearInterval(this._clock)
    },

    methods: {
        // Vietnam time; $i18n.locale 'en_ph' is not a valid locale tag for toLocale*String (RangeError)
        timeText(d) {
            const time = formatVnTime(d, { hour: '2-digit', minute: '2-digit' })
            const [, month, day] = vnDay(d).split('-')
            return vnDay(d) === vnDay(new Date(this.now)) ? time : `${time} ${day}/${month}`
        },

        async onPayNow() {
            this.payingNow = true
            try {
                const res = await apiPayments.createVnpayPayment(this.order.id)
                if (res?.data?.payment_url) {
                    // window.open(res.data.payment_url, '_blank')
                    window.location.href = res.data.payment_url
                    return
                }
                this.$q.notify({ type: 'negative', message: this.$t('order_detail.error_payment_create'), position: 'top' })
            } catch (e) {
                console.error('Pay now failed:', e)
                if (e.status === 409) {
                    // the previous VNPay payment went through, or is still being processed (T125):
                    // the message is already shown; reload the order so a paid one shows as paid
                    await this.orderStore.getOrderDetail(this.order.id, { silent: true })
                    return
                }
                this.$q.notify({ type: 'negative', message: this.$t('order_detail.error_payment_failed'), position: 'top' })
            } finally {
                this.payingNow = false
            }
        },

        async onCancelOrder() {
            this.cancelling = true
            try {
                await this.orderStore.cancelOrder(this.order.id)
                this.showCancelDialog = false
            } catch (e) {
                this.$q.notify({ type: 'negative', message: this.$t('order_detail.error_cancel_failed'), position: 'top' })
            } finally {
                this.cancelling = false
            }
        }
    }
}
</script>

<template>
    <div v-if="hasActions" class="actions">
        <q-btn v-if="isPaymentPending" class="btn-pay-now" dense no-caps :loading="payingNow" @click="onPayNow">
            <CreditCard style="margin-right: 8px" :size="18" />
            {{ $t('order_detail.btn_pay_now', { amount: totalText }) }}
        </q-btn>

        <div v-if="lateCancelAt && !canLateCancel" class="late-hint">
            {{ $t('order_detail.late_cancel_hint', { time: timeText(lateCancelAt) }) }}
        </div>

        <div v-if="canCancelPending && cancelBefore" class="late-hint">
            {{ $t('order_detail.cancel_until_hint', { time: timeText(cancelBefore) }) }}
        </div>

        <q-btn v-if="canCancelPending || canLateCancel" class="btn-cancel" flat dense no-caps @click="showCancelDialog = true">
            {{ canLateCancel ? $t('order_detail.btn_late_cancel') : $t('order_detail.btn_cancel') }}
        </q-btn>

        <!-- Cancel Confirmation Dialog -->
        <q-dialog v-model="showCancelDialog">
            <q-card class="cancel-dialog">
                <q-card-section>
                    <div class="dialog-title">{{ $t('order_detail.dialog_cancel_title') }}</div>
                    <div class="dialog-text">{{ $t('order_detail.dialog_cancel_text') }}</div>
                </q-card-section>
                <q-card-actions align="right">
                    <q-btn flat no-caps :label="$t('order_detail.dialog_keep')" v-close-popup />
                    <q-btn flat no-caps :label="$t('order_detail.dialog_confirm_cancel')" color="negative" :loading="cancelling" @click="onCancelOrder" />
                </q-card-actions>
            </q-card>
        </q-dialog>
    </div>
</template>

<style lang="scss" scoped>
.actions {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.btn-pay-now {
    width: 100%;
    background-color: #10b981;
    color: #fff;
    padding: 14px 0;
    border-radius: 2rem;
    font-weight: 600;
    font-size: 16px;
}

.btn-cancel {
    width: 100%;
    color: rgba(239, 68, 68, 0.7);
    font-weight: 500;
    font-size: 14px;
    padding: 10px 0;
}

.late-hint {
    font-size: 13px;
    text-align: center;
    color: rgba(255, 255, 255, 0.6);
}

.cancel-dialog {
    background-color: #1f2940;
    border-radius: 16px;
    min-width: 280px;
}

.dialog-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 8px;
}

.dialog-text {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.5);
}
</style>
