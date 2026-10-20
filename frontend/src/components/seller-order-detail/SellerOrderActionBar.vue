<script>
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import { AlertTriangle } from 'lucide-vue-next';
import { minutesUntilReady, formatWait, confirmEarlyReady, deadlineHint } from '@/utils/readyWindow';
import { SUPPORT_EMAIL, SUPPORT_MAILTO } from '@/utils/support';

const STATUS_NEXT = {
    pending:   'confirmed',
    confirmed: 'ready',
    ready:     'done',
}

const REJECT_REASONS = ['out_of_ingredients', 'too_busy', 'store_closing', 'other']

// Trip over: before that the Lalamove COMPLETED webhook closes the order, not the seller.
const DELIVERY_ENDED = ['COMPLETED', 'REJECTED', 'CANCELLED', 'CANCELED', 'EXPIRED']

export default {
    components: { AlertTriangle },

    name: 'SellerOrderActionBar',

    props: {
        order: { type: Object, required: true },
        delivery: { type: Object, default: null },
    },

    data() {
        return {
            showRejectDialog: false,
            selectedReason: '',
            customReason: '',
            rejecting: false,
            accepting: false,
            rebooking: false,
            rebookError: false,
            tick: 0,
            supportEmail: SUPPORT_EMAIL,
            supportMailto: SUPPORT_MAILTO,
            _tickInterval: null,
        }
    },

    computed: {
        canAccept() { return !!STATUS_NEXT[this.order.status] && !this.tripRunning },
        // Unknown delivery (not loaded yet) counts as running, so Done never flashes up.
        tripRunning() {
            return this.order.status === 'ready' && this.order.delivery_method === 'delivery'
                && !DELIVERY_ENDED.includes(this.delivery?.status)
        },
        readyWaitMinutes() {
            void this.tick
            return minutesUntilReady(this.order)
        },
        canReject()  { return ['pending', 'confirmed'].includes(this.order.status) },
        deadlineHint() {
            void this.tick
            return this.canAccept ? deadlineHint(this, this.order) : null
        },
        rebookCount() { return this.delivery?.rebook_count || 0 },
        rebookMax() { return this.delivery?.rebook_max || 3 },  // admin_settings.seller_rebook_max
        canRebook() {
            return this.order.status === 'delivery_failed' && this.rebookCount < this.rebookMax
        },
        maxRebookReached() {
            return this.order.status === 'delivery_failed' && this.rebookCount >= this.rebookMax
        },

        isDeliveryStuck() {
            void this.tick
            if (!this.delivery?.created_at) return false
            if (this.delivery.status !== 'ASSIGNING_DRIVER') return false
            return Date.now() - new Date(this.delivery.created_at).getTime() > 15 * 60 * 1000
        },

        showContactAdmin() {
            return this.rebookError || this.isDeliveryStuck
        },

        acceptLabel() {
            const map = {
                pending:   'seller_order_detail.action_accept_order',
                confirmed: 'seller_order_detail.action_mark_ready',
                ready:     'seller_order_detail.action_mark_done',
            }
            return map[this.order.status] ? this.$t(map[this.order.status]) : ''
        },

        rejectReasonOptions() {
            return REJECT_REASONS.map(key => ({
                key,
                label: this.$t(`seller_dashboard.reject_reason_${key}`),
            }))
        },

        rejectReasonText() {
            if (this.selectedReason === 'other') return this.customReason
            return this.rejectReasonOptions.find(o => o.key === this.selectedReason)?.label || ''
        },

        canConfirmReject() {
            if (!this.selectedReason) return false
            if (this.selectedReason === 'other' && !this.customReason.trim()) return false
            return !this.rejecting
        },
    },

    mounted() {
        this._tickInterval = setInterval(() => { this.tick++ }, 60_000)
    },

    beforeUnmount() {
        clearInterval(this._tickInterval)
    },

    methods: {
        formatWait,

        async onAccept() {
            const nextStatus = STATUS_NEXT[this.order.status]
            if (!nextStatus) return
            if (!await confirmEarlyReady(this, this.order)) return
            this.accepting = true
            try {
                await useDashboardStore().setOrderStatus(this.order.id, nextStatus)
                this.$q.notify({ classes: 'quasar-notify-positive', message: this.$t('seller_order_detail.toast_order_updated'), position: 'bottom', timeout: 1500 })
            } catch (e) {
                console.error('SellerOrderActionBar - onAccept -', e)
                this.$q.notify({ type: 'negative', message: this.$t('seller_order_detail.toast_update_failed'), position: 'bottom' })
            } finally {
                this.accepting = false
            }
        },

        async onSelfDeliver() {
            this.accepting = true
            try {
                await useDashboardStore().setOrderStatus(this.order.id, 'done')
                this.$q.notify({ classes: 'quasar-notify-positive', message: this.$t('seller_order_detail.toast_order_updated'), position: 'bottom', timeout: 1500 })
            } catch (e) {
                console.error('SellerOrderActionBar - onSelfDeliver -', e)
                this.$q.notify({ type: 'negative', message: this.$t('seller_order_detail.toast_update_failed'), position: 'bottom' })
            } finally {
                this.accepting = false
            }
        },

        async onCancelDueToNoDriver() {
            this.rejecting = true
            try {
                const reason = this.$t('seller_order_detail.cancel_reason_no_driver')
                await useDashboardStore().setOrderStatus(this.order.id, 'cancelled', reason)
                this.$q.notify({ classes: 'quasar-notify-positive', message: this.$t('seller_order_detail.toast_order_rejected'), position: 'bottom', timeout: 1500 })
            } catch (e) {
                console.error('SellerOrderActionBar - onCancelDueToNoDriver -', e)
                this.$q.notify({ type: 'negative', message: this.$t('seller_order_detail.toast_update_failed'), position: 'bottom' })
            } finally {
                this.rejecting = false
            }
        },

        async onRebook() {
            this.rebooking = true
            this.rebookError = false
            try {
                await useDashboardStore().doRebookDelivery(this.order.id)
                this.$q.notify({ classes: 'quasar-notify-positive', message: this.$t('seller_order_detail.toast_rebook_success'), position: 'bottom', timeout: 1500 })
            } catch (e) {
                this.rebookError = true
                console.error('SellerOrderActionBar - onRebook -', e)
                this.$q.notify({ type: 'negative', message: this.$t('seller_order_detail.toast_rebook_failed'), position: 'bottom' })
            } finally {
                this.rebooking = false
            }
        },

        async confirmReject() {
            if (!this.canConfirmReject) return
            this.rejecting = true
            try {
                await useDashboardStore().setOrderStatus(this.order.id, 'cancelled', this.rejectReasonText)
                this.showRejectDialog = false
                this.$q.notify({ classes: 'quasar-notify-positive', message: this.$t('seller_order_detail.toast_order_rejected'), position: 'bottom', timeout: 1500 })
            } catch (e) {
                console.error('SellerOrderActionBar - confirmReject -', e)
                this.$q.notify({ type: 'negative', message: this.$t('seller_order_detail.toast_reject_failed'), position: 'bottom' })
            } finally {
                this.rejecting = false
            }
        },
    },
}
</script>

<template>
    <div>
        <!-- Contact admin notice — infra errors requiring admin intervention -->
        <a v-if="showContactAdmin" :href="supportMailto" class="contact-admin-notice">
            {{ $t('seller_order_detail.contact_admin_notice', { email: supportEmail }) }}
        </a>

        <!-- Action buttons -->
        <div class="action-row">
            <template v-if="canAccept || canReject">
                <q-btn v-if="canReject" flat no-caps class="btn-reject" @click="showRejectDialog = true">
                    {{ $t('seller_order_detail.action_reject') }}
                </q-btn>
                <q-btn v-if="canAccept" unelevated no-caps class="btn-accept" :loading="accepting" @click="onAccept">
                    {{ readyWaitMinutes ? $t('seller_order_detail.ready_available_in', { time: formatWait(readyWaitMinutes) }) : acceptLabel }}
                </q-btn>
            </template>
            <template v-else-if="order.status === 'delivery_failed'">
                <template v-if="canRebook">
                    <q-btn unelevated no-caps class="btn-rebook" :loading="rebooking" @click="onRebook">
                        {{ $t('seller_order_detail.action_rebook_delivery') }} ({{ rebookCount + 1 }}/{{ rebookMax }})
                    </q-btn>
                </template>
                <template v-else-if="maxRebookReached">
                    <div class="cancel-block">
                        <div class="no-driver-notice">{{ $t('seller_order_detail.no_driver_notice') }}</div>
                        <div class="cancel-block-actions">
                            <q-btn unelevated no-caps class="btn-cancel-order" :loading="rejecting" @click="onCancelDueToNoDriver">
                                {{ $t('seller_order_detail.action_cancel_order') }}
                            </q-btn>
                            <q-btn unelevated no-caps class="btn-self-deliver" :loading="accepting" @click="onSelfDeliver">
                                {{ $t('seller_order_detail.action_self_deliver') }}
                            </q-btn>
                        </div>
                    </div>
                </template>
            </template>
            <div v-else-if="order.status === 'ready'" class="status-message">
                {{ $t('seller_order_detail.action_bar_driver_on_way') }}
            </div>
            <div v-else-if="order.status === 'done'"      class="status-message">{{ $t('seller_order_detail.action_bar_completed') }}</div>
            <div v-else-if="order.status === 'cancelled'" class="status-message cancelled">{{ $t('seller_order_detail.action_bar_cancelled') }}</div>
        </div>

        <div v-if="deadlineHint" class="deadline-hint" :class="{ urgent: deadlineHint.urgent }">
            <AlertTriangle :size="14" /> {{ deadlineHint.text }}
        </div>

        <!-- Reject dialog -->
        <q-dialog v-model="showRejectDialog">
            <q-card class="reject-dialog">
                <q-card-section>
                    <div class="dialog-title">{{ $t('seller_order_detail.reject_dialog_title') }}</div>
                    <div class="dialog-sub">{{ $t('seller_order_detail.reject_dialog_sub') }}</div>
                    <div class="reason-options">
                        <button
                            v-for="opt in rejectReasonOptions"
                            :key="opt.key"
                            class="reason-chip"
                            :class="{ active: selectedReason === opt.key }"
                            @click="selectedReason = opt.key"
                        >
                            {{ opt.label }}
                        </button>
                    </div>
                    <q-input
                        v-if="selectedReason === 'other'"
                        v-model="customReason"
                        dense outlined dark autofocus
                        :placeholder="$t('seller_order_detail.reject_reason_placeholder')"
                        class="custom-reason-input"
                    />
                </q-card-section>
                <q-card-actions align="right">
                    <q-btn flat no-caps :label="$t('common.button_label_cancel')" v-close-popup />
                    <q-btn flat no-caps color="negative" :label="$t('seller_order_detail.reject_confirm')"
                        :disable="!canConfirmReject" :loading="rejecting" @click="confirmReject" />
                </q-card-actions>
            </q-card>
        </q-dialog>
    </div>
</template>

<style lang="scss" scoped>
.contact-admin-notice {
    display: block;
    text-decoration: underline;
    font-size: 12px;
    color: var(--text-secondary);
    text-align: center;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    margin-bottom: 10px;
    line-height: 1.5;
}

.deadline-hint {
    margin-top: 8px;
    justify-content: center;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 4px;
    font-weight: 600;
    color: #facc15;

    &.urgent {
        color: #f87171;
    }
}

.action-row {
    display: flex;
    gap: 10px;
}

.btn-accept {
    flex: 1;
    background: var(--color-accent);
    color: #121b2f;
    font-weight: 700;
    font-size: 14px;
    border-radius: 12px;
    padding: 12px;
}

.btn-reject {
    color: #ef4444;
    font-size: 14px;
    padding: 12px 16px;
    border-radius: 12px;
    border: 1px solid rgba(239, 68, 68, 0.3);
}

.status-message {
    flex: 1;
    text-align: center;
    font-size: 14px;
    color: var(--text-secondary);
    padding: 12px 0;
}

.cancelled { color: #ef4444; }
.delivery-failed { color: #f59e0b; }

.btn-rebook {
    flex: 1;
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
    font-weight: 700;
    font-size: 14px;
    border-radius: 12px;
    padding: 12px;
}

.cancel-block {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.no-driver-notice {
    font-size: 13px;
    color: #ef4444;
    text-align: center;
}

.cancel-block-actions {
    display: flex;
    gap: 8px;
}

.btn-cancel-order {
    flex: 1;
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
    font-weight: 700;
    font-size: 14px;
    border-radius: 12px;
    padding: 12px;
}

.btn-self-deliver {
    flex: 1;
    background: var(--color-accent);
    color: #121b2f;
    font-weight: 700;
    font-size: 14px;
    border-radius: 12px;
    padding: 12px;
}

.reject-dialog {
    background: #1f2940;
    border-radius: 16px;
    min-width: 300px;
    color: var(--text-primary);
}

.dialog-title { font-size: 17px; font-weight: 700; margin-bottom: 4px; }
.dialog-sub   { font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; }

.reason-options {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;
}

.reason-chip {
    padding: 8px 14px;
    border-radius: 20px;
    border: 1px solid rgba(255,255,255,0.12);
    background: rgba(255,255,255,0.05);
    color: var(--text-primary);
    font-size: 13px;
    cursor: pointer;
    font-family: inherit;
    &.active {
        border-color: var(--color-accent);
        background: rgba(245,166,35,0.15);
        color: var(--color-accent);
    }
}

.custom-reason-input { margin-top: 8px; }
</style>
