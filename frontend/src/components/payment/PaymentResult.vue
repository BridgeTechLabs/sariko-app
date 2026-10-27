<script>
import { CircleCheckBig, CircleX, Clock } from 'lucide-vue-next';
import apiPayments from '@/apis/payments/apiPayments';

const POLL_INTERVAL = 3000;
const DEFAULT_WAIT_SECONDS = 90;   // until /payment-status gives admin_settings.payment_result_wait_seconds

// T125: the page trusts VNPay's SIGNED return result, never a timeout. Signed 00 = paid, waiting for the
// order to be confirmed (IPN, or the backend's VNPay check); signed other code = not paid; anything else
// or no confirmation in time = "waiting for VNPay". It never says "failed" because the IPN is late.
export default {
    components: {
        CircleCheckBig, CircleX, Clock
    },

    data() {
        return {
            // 'verifying' | 'confirming' | 'waiting' | 'failed'
            state: 'verifying',
            responseCode: '',
            orderId: '',
            pollTimer: null,
            waitSeconds: DEFAULT_WAIT_SECONDS,
            startedAt: 0,
        }
    },

    methods: {
        startPolling() {
            if (!this.orderId) return
            this.startedAt = Date.now()
            this.pollTimer = setInterval(async () => {
                try {
                    const res = await apiPayments.pollPaymentStatus(this.orderId)
                    if (res?.data?.wait_seconds) this.waitSeconds = res.data.wait_seconds
                    if (res?.data?.payment_status === 'paid') {
                        this.stopPolling()
                        this.$router.replace(`/orders/${this.orderId}`)
                        return
                    }
                } catch (e) {
                    console.error('Payment poll error:', e)   // keep polling on a network error
                }
                if (Date.now() - this.startedAt > this.waitSeconds * 1000) {
                    this.stopPolling()
                    this.state = 'waiting'
                }
            }, POLL_INTERVAL)
        },

        stopPolling() {
            if (this.pollTimer) {
                clearInterval(this.pollTimer)
                this.pollTimer = null
            }
        },
    },

    async created() {
        const params = new URLSearchParams(window.location.search)
        const txnRef = params.get('vnp_TxnRef')
        const orderIdNoDash = txnRef ? txnRef.split('_')[0] : ''
        this.orderId = orderIdNoDash.length === 32
            ? `${orderIdNoDash.slice(0,8)}-${orderIdNoDash.slice(8,12)}-${orderIdNoDash.slice(12,16)}-${orderIdNoDash.slice(16,20)}-${orderIdNoDash.slice(20)}`
            : ''

        let result = null
        try {
            const vnpParams = new URLSearchParams()
            for (const [key, value] of params) {
                if (key.startsWith('vnp_')) vnpParams.append(key, value)
            }
            result = (await apiPayments.checkVnpayReturn(vnpParams.toString()))?.data
        } catch (e) {
            console.error('Payment return error:', e)
        }

        this.responseCode = result?.response_code || ''
        if (result?.not_charged) {   // signed, and a code that means no money was taken (24, 51, ...)
            this.state = 'failed'
            return
        }
        // signed 00 → confirming; anything else (07 charged-but-flagged, 99, unsigned, missing) → waiting,
        // but still watch for the payment
        this.state = result?.is_valid && result.response_code === '00' ? 'confirming' : 'waiting'
        this.startPolling()
    },

    beforeUnmount() {
        this.stopPolling()
    },
}
</script>

<template>
    <div class="payment-result">

        <div v-if="state === 'verifying'" class="state-container">
            <q-spinner-hourglass color="yellow" size="5em" />
            <div class="title">{{ $t('payment.verifying') }}</div>
        </div>

        <div v-else-if="state === 'confirming'" class="state-container">
            <CircleCheckBig :size="64" color="#10b981" />
            <div class="title">{{ $t('payment.paidConfirming') }}</div>
            <q-spinner-dots color="yellow" size="2em" />
            <div class="subtext">{{ $t('payment.doNotClose') }}</div>
        </div>

        <div v-else-if="state === 'waiting'" class="state-container">
            <Clock :size="64" color="#f59e0b" />
            <div class="title">{{ $t('payment.waitingTitle') }}</div>
            <div class="subtext">{{ $t('payment.waitingMessage') }}</div>
            <q-btn class="btn-primary" dense no-caps @click="$router.push(orderId ? `/orders/${orderId}` : '/orders')">
                {{ $t('payment.viewOrders') }}
            </q-btn>
        </div>

        <div v-else class="state-container">
            <CircleX :size="64" color="#ef4444" />
            <div class="title">{{ $t('payment.failed') }}</div>
            <div class="subtext">{{ $t('payment.failedMessage') }}</div>
            <div v-if="responseCode" class="error-code">
                Error code: {{ responseCode }}
            </div>
            <q-btn class="btn-primary" dense no-caps @click="$router.push(orderId ? `/orders/${orderId}` : '/orders')">
                {{ $t('payment.payAgain') }}
            </q-btn>
            <q-btn class="btn-secondary" flat dense no-caps @click="$router.push('/home')">
                {{ $t('payment.backHome') }}
            </q-btn>
        </div>
    </div>
</template>

<style lang="scss" scoped>
.payment-result {
    width: 100%;
}

.state-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 12px;
}

.title {
    font-family: $sariko-font-family-primary;
    font-size: 22px;
    font-weight: 700;
    margin-top: 8px;
}

.subtext {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.5);
    line-height: 1.5;
    max-width: 300px;
}

.error-code {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.3);
    margin-bottom: 8px;
}

.btn-primary {
    width: 100%;
    max-width: 280px;
    background-color: $accent;
    color: var(--bg-main);
    padding: 14px 0;
    border-radius: 2rem;
    font-weight: 600;
    font-size: 16px;
    margin-top: 12px;
}

.btn-secondary {
    color: rgba(255, 255, 255, 0.6);
    font-size: 14px;
}
</style>
