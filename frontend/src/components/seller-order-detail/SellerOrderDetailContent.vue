<script>
import { Phone } from 'lucide-vue-next';

const STATUS_DISPLAY_KEY = {
    pending:   'seller_order_detail.status_new',
    confirmed: 'seller_order_detail.status_preparing',
    ready:     'seller_order_detail.status_ready',
    done:      'seller_order_detail.status_done',
    cancelled: 'seller_order_detail.status_cancelled',
}

const STATUS_CLASS = {
    pending:   'badge-new',
    confirmed: 'badge-preparing',
    ready:     'badge-ready',
    done:      'badge-done',
    cancelled: 'badge-cancelled',
}

const DELIVERY_STATUS_ORDER = ['ASSIGNING_DRIVER', 'ON_GOING', 'PICKED_UP', 'COMPLETED']
const DELIVERY_CANCELLED_STATUSES = ['CANCELED', 'REJECTED', 'EXPIRED']
const DELIVERY_CANCEL_ERROR_KEY = {
    REJECTED: 'seller_order_detail.delivery_rejected_error',
    EXPIRED:  'seller_order_detail.delivery_expired_error',
    CANCELED: 'seller_order_detail.delivery_canceled_error',
}

export default {
    name: 'SellerOrderDetailContent',

    components: { Phone },

    props: {
        order: {
            type: Object,
            required: true,
        },
        delivery: {
            type: Object,
            default: null,
        },
    },

    computed: {
        displayStatus() {
            return STATUS_DISPLAY_KEY[this.order.status] ? this.$t(STATUS_DISPLAY_KEY[this.order.status]) : this.order.status
        },

        statusClass() {
            return STATUS_CLASS[this.order.status] || ''
        },

        customerName() {
            return this.order.users?.name || this.order.users?.email || 'Customer'
        },

        customerPhone() {
            return this.order.users?.phone || null
        },

        subtotal() {
            return (this.order.order_items || []).reduce(
                (sum, i) => sum + (i.price_snapshot * i.quantity), 0
            )
        },

        timelineSteps() {
            const isCancelled = this.order.status === 'cancelled'
            const orderStatusIdx = { pending: 0, confirmed: 1, ready: 2, done: 3 }
            const currentOrderIdx = orderStatusIdx[this.order.status] ?? -1
            const hasDelivery = this.order.delivery_method === 'delivery' && !!this.delivery
            const deliveryCancelled = hasDelivery && DELIVERY_CANCELLED_STATUSES.includes(this.delivery.status)
            const deliveryIdx = hasDelivery ? DELIVERY_STATUS_ORDER.indexOf(this.delivery.status) : -1

            const steps = []

            // --- Order steps ---
            const orderSteps = [
                { key: 'pending',   label: this.$t('seller_order_detail.timeline_placed') },
                { key: 'confirmed', label: this.$t('seller_order_detail.timeline_accepted') },
                { key: 'ready',     label: this.$t('seller_order_detail.timeline_ready') },
            ]
            orderSteps.forEach((step, idx) => {
                const isReadyStep = step.key === 'ready'
                // When delivery is active, 'ready' step is done (delivery phase started)
                const done = !isCancelled && (hasDelivery && isReadyStep ? true : currentOrderIdx > idx)
                // 'ready' is current only when no delivery and order is at ready status
                const current = !isCancelled && !hasDelivery && currentOrderIdx === idx
                steps.push({ key: step.key, label: step.label, done, current, error: false, errorMessage: null })
            })

            if (hasDelivery) {
                // "Delivery order created" — always done once delivery row exists
                steps.push({
                    key: 'delivery_created',
                    label: this.$t('seller_order_detail.delivery_step_created'),
                    done: true, current: false, error: false, errorMessage: null,
                })

                if (deliveryCancelled) {
                    // Show assigning rider as the failed step, hide the rest
                    const errorKey = DELIVERY_CANCEL_ERROR_KEY[this.delivery.status] || 'seller_order_detail.delivery_cancelled_error'
                    steps.push({
                        key: 'ASSIGNING_DRIVER',
                        label: this.$t('seller_order_detail.delivery_step_assigning'),
                        done: false, current: false, error: true,
                        errorMessage: this.$t(errorKey),
                    })
                } else {
                    const deliveryStepDefs = [
                        { key: 'ASSIGNING_DRIVER', label: this.$t('seller_order_detail.delivery_step_assigning') },
                        { key: 'ON_GOING',         label: this.$t('seller_order_detail.delivery_step_ongoing') },
                        { key: 'PICKED_UP',        label: this.$t('seller_order_detail.delivery_step_pickedup') },
                        { key: 'COMPLETED',        label: this.$t('seller_order_detail.delivery_step_completed') },
                    ]
                    deliveryStepDefs.forEach((step, i) => {
                        const isLast = i === deliveryStepDefs.length - 1
                        steps.push({
                            key: step.key, label: step.label,
                            // Last step (COMPLETED) has nothing after it, so mark it done once reached
                            done: deliveryIdx > i || (isLast && deliveryIdx === i),
                            current: deliveryIdx === i,
                            error: false, errorMessage: null,
                        })
                    })
                }
            } else {
                // Non-delivery: show "Delivered/Done" final step
                steps.push({
                    key: 'done',
                    label: this.$t('seller_order_detail.timeline_delivered'),
                    done: !isCancelled && this.order.status === 'done',
                    current: !isCancelled && this.order.status === 'done',
                    error: false, errorMessage: null,
                })
            }

            return steps
        },
    },

    methods: {
        fmt(amount) {
            return new Intl.NumberFormat('vi-VN').format(amount || 0) + ' ₫'
        },
    },
}
</script>

<template>
    <div class="detail-content">

        <!-- Status -->
        <div class="card">
            <div class="card-row">
                <span class="section-label">{{ $t('seller_order_detail.section_status') }}</span>
                <span class="status-badge" :class="statusClass">{{ displayStatus }}</span>
            </div>
            <div v-if="order.status === 'cancelled' && order.cancellation_reason" class="cancellation-reason">
                {{ $t('seller_order_detail.label_reason') }}: {{ order.cancellation_reason }}
            </div>
            <div class="order-time-text">
                {{ $t('seller_order_detail.label_placed') }} {{ new Date(order.created_at).toLocaleString('vi-VN') }}
            </div>
        </div>

        <!-- Customer -->
        <div class="card">
            <div class="section-label" style="margin-bottom:12px;">{{ $t('seller_order_detail.section_customer') }}</div>
            <div class="info-row">
                <span class="info-key">{{ $t('seller_order_detail.label_name') }}</span>
                <span class="info-val">{{ customerName }}</span>
            </div>
            <div v-if="customerPhone" class="info-row">
                <span class="info-key">{{ $t('seller_order_detail.label_phone') }}</span>
                <a :href="`tel:${customerPhone}`" class="phone-link">
                    <Phone :size="13" style="margin-right:4px;" />{{ customerPhone }}
                </a>
            </div>
            <div v-if="order.delivery_address" class="info-row">
                <span class="info-key">{{ $t('seller_order_detail.label_address') }}</span>
                <span class="info-val">{{ order.delivery_address }}</span>
            </div>
            <div v-if="order.note" class="info-row">
                <span class="info-key">{{ $t('seller_order_detail.label_note') }}</span>
                <span class="info-val note-text">{{ order.note }}</span>
            </div>
        </div>

        <!-- Items -->
        <div class="card">
            <div class="section-label" style="margin-bottom:12px;">{{ $t('seller_order_detail.section_items') }}</div>
            <div v-for="item in order.order_items" :key="item.id" class="item-row">
                <span class="item-name">{{ item.quantity }}x {{ item.name_snapshot }}<span v-if="item.variant_name_snapshot" class="order-variant"> ({{ item.variant_name_snapshot }})</span></span>
                <span class="item-price">{{ fmt(item.price_snapshot * item.quantity) }}</span>
            </div>
            <q-separator style="background:rgba(255,255,255,0.08);margin:12px 0;" />
            <div class="item-row">
                <span class="info-key">{{ $t('seller_order_detail.label_subtotal') }}</span>
                <span class="info-val">{{ fmt(subtotal) }}</span>
            </div>
            <div v-if="order.delivery_fee" class="item-row">
                <span class="info-key">{{ $t('seller_order_detail.label_delivery_fee') }}</span>
                <span class="info-val">{{ fmt(order.delivery_fee) }}</span>
            </div>
            <div class="item-row total-row">
                <span>{{ $t('seller_order_detail.label_total') }}</span>
                <span>{{ fmt(order.total_amount) }}</span>
            </div>
        </div>

        <!-- Payment -->
        <div class="card">
            <div class="section-label" style="margin-bottom:12px;">{{ $t('seller_order_detail.section_payment') }}</div>
            <div class="info-row">
                <span class="info-key">{{ $t('seller_order_detail.label_method') }}</span>
                <span class="info-val">{{ order.payment_method || 'VNPay' }}</span>
            </div>
            <div class="info-row">
                <span class="info-key">{{ $t('seller_order_detail.label_status') }}</span>
                <span class="info-val" :style="{ color: order.payment_status === 'paid' ? 'var(--color-success)' : 'var(--color-warning)' }">
                    {{ order.payment_status === 'paid' ? $t('seller_order_detail.payment_paid') : $t('seller_order_detail.payment_pending') }}
                </span>
            </div>
        </div>

        <!-- Unified Timeline -->
        <div class="card">
            <div class="section-label" style="margin-bottom:16px;">{{ $t('seller_order_detail.section_timeline') }}</div>
            <div class="timeline">
                <div v-for="(step, idx) in timelineSteps" :key="step.key" class="timeline-step">
                    <div class="timeline-left">
                        <div class="timeline-dot" :class="{ done: step.done, current: step.current, error: step.error }"></div>
                        <div v-if="idx < timelineSteps.length - 1" class="timeline-line" :class="{ done: step.done }"></div>
                    </div>
                    <div class="timeline-right">
                        <div
                            class="timeline-label"
                            :class="{
                                'label-done':    step.done,
                                'label-current': step.current && !step.error,
                                'label-future':  !step.done && !step.current && !step.error,
                                'label-error':   step.error,
                            }"
                        >
                            {{ step.label }}
                        </div>
                        <div v-if="step.errorMessage" class="delivery-error-inline">
                            {{ step.errorMessage }}
                        </div>
                    </div>
                </div>
            </div>
        </div>

    </div>
</template>

<style lang="scss" scoped>
.detail-content {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.card {
    background: rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    padding: 16px;
}

.card-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.section-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.status-badge {
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 12px;
}

.badge-new       { background: rgba(245,158,11,0.15); color: var(--color-warning); }
.badge-preparing { background: rgba(59,130,246,0.15);  color: var(--color-info); }
.badge-ready     { background: rgba(139,92,246,0.15);  color: #a78bfa; }
.badge-done      { background: rgba(34,197,94,0.15);   color: var(--color-success); }
.badge-cancelled { background: rgba(239,68,68,0.1);    color: #ef4444; }

.order-time-text, .cancellation-reason {
    font-size: 12px;
    color: var(--text-muted);
}

.cancellation-reason { color: #ef4444; margin-bottom: 4px; }

.info-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 8px;
    &:last-child { margin-bottom: 0; }
}

.info-key { font-size: 13px; color: var(--text-muted); flex-shrink: 0; }
.info-val  { font-size: 13px; color: var(--text-primary); text-align: right; }
.note-text { font-style: italic; color: var(--text-secondary); }

.phone-link {
    display: flex;
    align-items: center;
    color: var(--color-accent);
    font-size: 13px;
    text-decoration: none;
}

.item-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    &:last-child { margin-bottom: 0; }
}

.item-name  { font-size: 14px; color: var(--text-primary); }
.item-price { font-size: 14px; color: var(--text-secondary); }

.total-row {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    margin-top: 4px;
}

/* Timeline */
.timeline { display: flex; flex-direction: column; }

.timeline-step {
    display: flex;
    gap: 12px;
}

.timeline-left {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 16px;
    flex-shrink: 0;
}

.timeline-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 2px solid rgba(255,255,255,0.2);
    background: transparent;
    flex-shrink: 0;
    &.done    { background: var(--color-success); border-color: var(--color-success); }
    &.current { border-color: var(--color-accent); background: rgba(245,166,35,0.3); }
    &.error   { border-color: #ef4444; background: rgba(239,68,68,0.25); }
}

.timeline-line {
    width: 2px;
    flex: 1;
    min-height: 24px;
    background: rgba(255,255,255,0.1);
    margin: 2px 0;
    &.done { background: var(--color-success); }
}

.timeline-right {
    flex: 1;
    padding-bottom: 20px;
    min-width: 0;
}

.timeline-label {
    font-size: 13px;
    color: var(--text-muted);
    &.label-done    { color: var(--text-primary); font-weight: 500; }
    &.label-current { color: var(--color-accent); font-weight: 600; }
    &.label-error   { color: #ef4444; font-weight: 600; }
}

.delivery-error-inline {
    margin-top: 8px;
    padding: 10px 12px;
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 10px;
    font-size: 12px;
    color: #f87171;
    line-height: 1.5;
}

.order-variant {
    color: #f5A623;
    font-weight: 600;
}
</style>
