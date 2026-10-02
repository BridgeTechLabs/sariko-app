<script>
import { Check, X, AlertTriangle, RefreshCw, Copy, User, Phone, MapPin } from 'lucide-vue-next';
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import apiSellerDashboard from '@/apis/sellers/apiSellerDashboard';
import apiDeliveries from '@/apis/deliveries/apiDeliveries';

const STATUS_DISPLAY_KEY = {
    pending:          'seller_home.status_new',
    confirmed:        'seller_home.status_preparing',
    delivery_failed:  'seller_home.status_delivery_failed',
}

const STATUS_NEXT = {
    pending: 'confirmed',
    confirmed: 'ready',
}

const REJECT_REASONS = [
    'out_of_ingredients',
    'too_busy',
    'store_closing',
    'other',
]

export default {
    name: 'ActionOrdersList',

    components: { Check, X, AlertTriangle, RefreshCw, Copy, User, Phone, MapPin },

    props: {
        orders: {
            type: Array,
            default: () => []
        }
    },

    data() {
        return {
            showRejectDialog: false,
            rejectingOrder: null,
            selectedReason: '',
            customReason: '',
            rejecting: false,
            orderErrors: {},      // { [orderId]: string[] }
            loadingOrders: {},    // { [orderId]: true }
            rebookingOrders: {},  // { [orderId]: true }
            rebookErrors: {},     // { [orderId]: 'max_attempts'|'error' }
            activeTab: 'today',
            copiedKey: null,
        }
    },

    computed: {
        sellerInfo() {
            return useDashboardStore().sellerInfo
        },
        deliveryStatuses() {
            return useDashboardStore().deliveryStatuses
        },

        todayStr() {
            return new Date().toDateString()
        },
        hasUpcoming() {
            return this.orders.some(o => o.delivery_appointment && new Date(o.delivery_appointment).toDateString() !== this.todayStr)
        },
        todayCount() {
            return this.orders.filter(o => {
                const isToday = !o.delivery_appointment || new Date(o.delivery_appointment).toDateString() === this.todayStr
                return isToday && ['pending', 'confirmed', 'delivery_failed'].includes(o.status)
            }).length
        },
        upcomingCount() {
            return this.orders.filter(o => {
                if (!o.delivery_appointment) return false
                if (new Date(o.delivery_appointment).toDateString() === this.todayStr) return false
                return ['pending', 'confirmed', 'delivery_failed'].includes(o.status)
            }).length
        },
        filteredByTab() {
            return this.orders.filter(order => {
                if (!order.delivery_appointment) return this.activeTab === 'today'
                const apptDay = new Date(order.delivery_appointment).toDateString()
                return this.activeTab === 'today' ? apptDay === this.todayStr : apptDay !== this.todayStr
            })
        },
        displayOrders() {
            return this.filteredByTab
                .filter(order => ['pending', 'confirmed', 'delivery_failed'].includes(order.status))
                .map(order => ({
                    ...order,
                    displayStatus: STATUS_DISPLAY_KEY[order.status] ? this.$t(STATUS_DISPLAY_KEY[order.status]) : order.status,
                    customerName: order.users?.name || order.users?.email || 'Customer',
                    items: order.order_items || [],
                    totalText: new Intl.NumberFormat('vi-VN').format(order.total_amount || 0) + ' ₫',
                    time: new Date(/[Z+]/.test(order.created_at) ? order.created_at : order.created_at + 'Z').toLocaleString(this.$i18n.locale === 'vi' ? 'vi-VN' : 'en-PH', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Ho_Chi_Minh', hour12: false }),
                    nextLabel: STATUS_NEXT[order.status] === 'confirmed' ? this.$t('seller_home.action_accept') : this.$t('seller_home.action_ready_delivery'),
                    appointmentText: order.delivery_appointment ? this.formatAppointment(order.delivery_appointment) : null,
                }))
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

    watch: {
        orders: {
            handler(newOrders) {
                newOrders
                    .filter(o => o.status === 'delivery_failed' && o.delivery_method === 'delivery')
                    .forEach(o => {
                        if (!this.deliveryStatuses[o.id]) this.fetchDeliveryStatus(o.id)
                    })
            },
            immediate: true,
        },
    },

    methods: {
        t(key, fallback) {
            if (typeof this.$t === 'function') return this.$t(key)
            return fallback || key
        },

        checkSellerReadiness() {
            const missing = []
            if (!this.sellerInfo?.has_address) missing.push(this.t('seller_home.missing_address', 'Store address is missing'))
            if (!this.sellerInfo?.has_phone) missing.push(this.t('seller_home.missing_phone', 'Phone number is missing'))
            return missing
        },

        async copyToClipboard(text, key) {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(text)
            } else {
                const el = document.createElement('textarea')
                el.value = text
                el.style.position = 'fixed'
                el.style.opacity = '0'
                document.body.appendChild(el)
                el.select()
                document.execCommand('copy')
                document.body.removeChild(el)
            }
            this.copiedKey = key
            setTimeout(() => { this.copiedKey = null }, 1500)
        },

        clearError(orderId) {
            delete this.orderErrors[orderId]
        },

        async fetchDeliveryStatus(orderId) {
            await useDashboardStore().fetchDeliveryStatus(orderId)
        },

        async onRebook(order) {
            if (this.rebookingOrders[order.id]) return
            this.rebookErrors = { ...this.rebookErrors, [order.id]: null }
            this.rebookingOrders = { ...this.rebookingOrders, [order.id]: true }
            try {
                await apiDeliveries.rebookDelivery(order.id)
                const prev = useDashboardStore().deliveryStatuses[order.id]
                useDashboardStore().setDeliveryStatus(order.id, {
                    status: 'ASSIGNING_DRIVER',
                    rebook_count: (prev?.rebook_count || 0) + 1,
                })
                this.$q.notify({ classes: 'quasar-notify-positive', message: this.$t('seller_home.toast_rebook_success'), position: 'bottom', timeout: 1500 })
            } catch (e) {
                console.error('ActionOrdersList - onRebook -', e)
                const detail = e?.response?.data?.detail || ''
                const errorType = detail.includes('rebook_count') ? 'max_attempts' : 'error'
                this.rebookErrors = { ...this.rebookErrors, [order.id]: errorType }
            } finally {
                const { [order.id]: _, ...rest } = this.rebookingOrders
                this.rebookingOrders = rest
            }
        },

        async onAccept(order) {
            const nextStatus = STATUS_NEXT[order.status]
            if (!nextStatus) return
            if (this.loadingOrders[order.id]) return

            // Pre-flight check: when marking ready (triggers Lalamove), validate seller info
            if (nextStatus === 'ready' && order.delivery_method === 'delivery') {
                const missing = this.checkSellerReadiness()
                if (missing.length > 0) {
                    this.orderErrors = { ...this.orderErrors, [order.id]: missing }
                    return
                }
            }
            this.clearError(order.id)
            this.loadingOrders = { ...this.loadingOrders, [order.id]: true }

            try {
                await apiSellerDashboard.updateOrderStatus(order.id, nextStatus)
                useDashboardStore().updateOrderLocally(order.id, nextStatus)
                this.$q.notify({
                    classes: 'quasar-notify-positive',
                    message: nextStatus === 'confirmed'
                        ? this.t('seller_home.toast_order_accepted', 'Order accepted!')
                        : this.t('seller_home.toast_order_ready', 'Delivery booked!'),
                    position: 'bottom',
                    timeout: 1500,
                })
            } catch (e) {
                console.error('ActionOrdersList - onAccept -', e)
                const errorMsg = e?.response?.data?.detail || this.t('seller_home.toast_update_failed', 'Failed to update order')
                this.orderErrors = { ...this.orderErrors, [order.id]: [errorMsg] }
            } finally {
                const { [order.id]: _, ...rest } = this.loadingOrders
                this.loadingOrders = rest
            }
        },

        fmt(amount) {
            return new Intl.NumberFormat('vi-VN').format(amount || 0) + ' ₫'
        },

        formatAppointment(isoStr) {
            if (!isoStr) return ''
            const d = new Date(isoStr)
            const locale = this.$i18n.locale === 'vi' ? 'vi-VN' : 'en-PH'
            return d.toLocaleString(locale, { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Ho_Chi_Minh', hour12: false })
        },

        openRejectDialog(order) {
            this.rejectingOrder = order
            this.selectedReason = ''
            this.customReason = ''
            this.showRejectDialog = true
        },

        async confirmReject() {
            if (!this.canConfirmReject || !this.rejectingOrder) return
            this.rejecting = true
            try {
                await apiSellerDashboard.updateOrderStatus(this.rejectingOrder.id, 'cancelled', this.rejectReasonText)
                useDashboardStore().updateOrderLocally(this.rejectingOrder.id, 'cancelled')
                this.showRejectDialog = false
                this.$q.notify({
                    classes: 'quasar-notify-positive',
                    message: this.t('seller_home.toast_order_rejected', 'Order rejected.'),
                    position: 'bottom',
                    timeout: 1500,
                })
            } catch (e) {
                console.error('ActionOrdersList - confirmReject -', e)
                this.$q.notify({
                    type: 'negative',
                    message: this.t('seller_home.toast_reject_failed', 'Failed to reject order'),
                    position: 'bottom',
                })
            } finally {
                this.rejecting = false
            }
        },
    },
}
</script>

<template>
    <div>
        <div v-if="hasUpcoming" class="schedule-tabs">
            <button
                class="tab-btn"
                :class="{ active: activeTab === 'today' }"
                @click="activeTab = 'today'"
            >
                <span class="tab-label">{{ $t('seller_home.tab_today') }}</span>
                <span v-if="todayCount > 0" class="tab-count">{{ todayCount }}</span>
            </button>
            <button
                class="tab-btn"
                :class="{ active: activeTab === 'upcoming' }"
                @click="activeTab = 'upcoming'"
            >
                <span class="tab-label">{{ $t('seller_home.tab_upcoming') }}</span>
                <span v-if="upcomingCount > 0" class="tab-count">{{ upcomingCount }}</span>
            </button>
        </div>

        <div v-if="displayOrders.length === 0" class="empty-state">
            <div class="empty-icon">🎉</div>
            <template v-if="activeTab === 'today'">
                <div class="empty-text">{{ $t('seller_home.empty_all_caught_up') }}</div>
                <div class="empty-sub">{{ $t('seller_home.empty_all_caught_up_sub') }}</div>
            </template>
            <template v-else>
                <div class="empty-text">{{ $t('seller_home.empty_tab_upcoming') }}</div>
                <div class="empty-sub">{{ $t('seller_home.empty_tab_upcoming_sub') }}</div>
            </template>
        </div>

        <!-- Order cards -->
        <div v-else class="orders-list">
            <div v-for="order in displayOrders" :key="order.id" class="order-card">
                <div class="order-header">
                    <div class="customer-name">{{ order.customerName }}</div>
                    <span class="status-badge" :class="order.status === 'pending' ? 'badge-new' : order.status === 'delivery_failed' ? 'badge-delivery-failed' : 'badge-preparing'">
                        {{ order.displayStatus }}
                    </span>
                </div>
                <div class="order-meta">
                    <div class="order-time"><span class="order-time-label">{{ $t('seller_home.label_ordered_at') }}</span> {{ order.time }}</div>
                    <div v-if="order.appointmentText" class="appointment-badge">
                        📅 <span class="order-time-label">{{ $t('seller_home.label_deliver_at') }}</span> {{ order.appointmentText }}
                    </div>
                </div>

                <q-separator style="background: rgba(255,255,255,0.08); margin: 10px 0;" />

                <!-- Items list -->
                <div v-for="item in order.items" :key="item.id" class="item-row">
                    <div class="item-left">
                        <span class="item-qty">{{ item.quantity }}</span>
                        <span class="item-sep">×</span>
                        <span class="item-name">{{ item.name_snapshot }}<span v-if="item.variant_name_snapshot" class="order-variant"> ({{ item.variant_name_snapshot }})</span></span>
                    </div>
                    <span class="item-price">{{ fmt(item.price_snapshot * item.quantity) }}</span>
                </div>

                <q-separator style="background: rgba(255,255,255,0.08); margin: 10px 0;" />

                
                <div v-if="order.delivery_fee > 0" class="item-row" style="opacity: 0.7;">
                    <span class="total-label">{{ $t('seller_home.delivery_fee') }}</span>
                    <span class="item-price">{{ fmt(order.delivery_fee) }}</span>
                </div>

                
                <div class="total-row">
                    <span class="total-label">{{ $t('seller_home.order_total') }}</span>
                    <span class="total-value">{{ order.totalText }}</span>
                </div>

                <!-- Error card -->
                <div v-if="orderErrors[order.id]" class="error-card">
                    <div class="error-card__header">
                        <AlertTriangle :size="16" />
                        <span>{{ $t('seller_home.error_missing_info') }}</span>
                    </div>
                    <ul class="error-card__list">
                        <li v-for="(msg, i) in orderErrors[order.id]" :key="i">{{ msg }}</li>
                    </ul>
                </div>

                <!-- Contact buyer — always visible -->
                <div class="order-actions">
                    <q-btn flat dense no-caps class="btn-contact">
                        <q-icon name="person" size="14px" style="margin-right:4px;" />
                        {{ $t('seller_home.action_contact_buyer') }}
                        <q-popup-proxy>
                            <div class="buyer-info-popup">
                                <div class="buyer-info-row">
                                    <span class="buyer-info-label"><User :size="11" /> {{ $t('seller_home.buyer_name') }}</span>
                                    <span>{{ order.customerName }}</span>
                                </div>
                                <div class="buyer-info-row">
                                    <span class="buyer-info-label"><Phone :size="11" /> {{ $t('seller_home.buyer_phone') }}</span>
                                    <div v-if="order.users?.phone" class="buyer-info-value">
                                        <span>{{ order.users.phone }}</span>
                                        <button class="btn-copy" @click.stop="copyToClipboard(order.users.phone, order.id + '_phone')">
                                            <Check v-if="copiedKey === order.id + '_phone'" :size="12" style="color:#4ade80" />
                                            <Copy v-else :size="12" />
                                        </button>
                                    </div>
                                    <span v-else class="buyer-info-na">N/A</span>
                                </div>
                                <div class="buyer-info-row">
                                    <span class="buyer-info-label"><MapPin :size="11" /> {{ $t('seller_home.buyer_address') }}</span>
                                    <div v-if="order.delivery_address" class="buyer-info-value">
                                        <span>{{ order.delivery_address }}</span>
                                        <button class="btn-copy" @click.stop="copyToClipboard(order.delivery_address, order.id + '_addr')">
                                            <Check v-if="copiedKey === order.id + '_addr'" :size="12" style="color:#4ade80" />
                                            <Copy v-else :size="12" />
                                        </button>
                                    </div>
                                    <span v-else class="buyer-info-na">N/A</span>
                                </div>
                            </div>
                        </q-popup-proxy>
                    </q-btn>

                    <!-- Non-ready: reject/accept on the right -->
                    <div v-if="order.status !== 'delivery_failed'" class="order-actions-right">
                        <q-btn flat dense no-caps class="btn-reject" :disable="!!loadingOrders[order.id]" @click="openRejectDialog(order)">
                            <X :size="14" style="margin-right: 4px;" /> {{ $t('seller_home.action_reject') }}
                        </q-btn>
                        <q-btn unelevated dense no-caps class="btn-accept" :loading="!!loadingOrders[order.id]" @click="onAccept(order)">
                            <Check :size="14" style="margin-right: 4px;" /> {{ order.nextLabel }}
                        </q-btn>
                    </div>
                </div>

                <!-- delivery_failed: rebook action (below contact row) -->
                <template v-if="order.status === 'delivery_failed'">
                    <div v-if="rebookErrors[order.id] === 'max_attempts' || rebookErrors[order.id] === 'error'" class="rebook-admin-notice">
                        {{ $t('seller_home.contact_admin_notice') }}
                    </div>
                    <div class="delivery-rebook-row">
                        <button class="btn-delivery-issue" @click="$router.push({ name: 'seller-order-detail', params: { orderId: order.id } })">
                            <AlertTriangle :size="13" />
                            {{ $t('seller_home.delivery_issue_details') }}
                        </button>
                        <q-btn
                            v-if="(deliveryStatuses[order.id]?.rebook_count || 0) < 3 && rebookErrors[order.id] !== 'max_attempts'"
                            unelevated dense no-caps
                            class="btn-rebook"
                            :loading="!!rebookingOrders[order.id]"
                            @click="onRebook(order)"
                        >
                            <RefreshCw :size="12" style="margin-right:4px;" />
                            {{ $t('seller_home.action_rebook') }}
                        </q-btn>
                    </div>
                </template>
            </div>
        </div>

        <!-- Reject Dialog -->
        <q-dialog v-model="showRejectDialog">
            <q-card class="reject-dialog">
                <q-card-section>
                    <div class="dialog-title">{{ $t('seller_home.reject_dialog_title') }}</div>
                    <div class="dialog-sub">{{ $t('seller_home.reject_dialog_sub') }}</div>
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
                        :placeholder="$t('seller_home.reject_reason_placeholder')"
                        class="custom-reason-input"
                    />
                </q-card-section>
                <q-card-actions align="right">
                    <q-btn flat no-caps :label="$t('common.button_label_cancel')" v-close-popup />
                    <q-btn flat no-caps color="negative" :label="$t('seller_home.reject_confirm')"
                        :disable="!canConfirmReject" :loading="rejecting" @click="confirmReject" />
                </q-card-actions>
            </q-card>
        </q-dialog>
    </div>
</template>

<style lang="scss" scoped>
.schedule-tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
}

.tab-btn {
    flex: 1;
    padding: 8px 0;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-secondary);
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s ease;
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
    gap: 6px;

    &.active {
        background: rgba(245, 166, 35, 0.15);
        border-color: rgba(245, 166, 35, 0.4);
        color: var(--color-accent);
    }
}

.tab-label {
    font-size: 13px;
    font-weight: 600;
}

.tab-count {
    font-size: 12px;
    font-weight: 700;
    background: var(--color-accent);
    color: #121b2f;
    border-radius: 10px;
    padding: 1px 7px;
    line-height: 1.6;
}

.appointment-badge {
    font-size: 11px;
    font-weight: 600;
    color: var(--color-accent);
    margin-top: 3px;
}

.empty-state {
    text-align: center;
    padding: 40px 0;
    color: var(--text-secondary);
}

.empty-icon {
    font-size: 40px;
    margin-bottom: 12px;
}

.empty-text {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.empty-sub {
    font-size: 13px;
}

.orders-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.order-card {
    background: rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    padding: 16px;
}

.order-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}

.customer-name {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
}

.order-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-top: 2px;
}

.order-time {
    font-size: 11px;
    color: var(--text-muted);
}

.order-time-label {
    opacity: 0.6;
}

.status-badge {
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 12px;
    flex-shrink: 0;
}

.badge-new {
    background: rgba(245, 158, 11, 0.15);
    color: var(--color-warning);
}

.badge-preparing {
    background: rgba(59, 130, 246, 0.15);
    color: var(--color-info);
}

.badge-delivery-failed {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
}

.item-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
}

.item-left {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: var(--text-secondary);
}

.item-qty {
    font-weight: 700;
    color: var(--text-primary);
}

.item-sep {
    color: var(--text-muted);
    font-size: 11px;
}

.item-name {
    font-weight: 600;
    color: var(--text-primary);
}

.item-price {
    font-size: 13px;
    color: var(--text-secondary);
}

.total-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.total-label {
    font-size: 13px;
    color: var(--text-muted);
    font-weight: 500;
}

.total-value {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
}

/* Inline error card */
.error-card {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.25);
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 12px;
}

.error-card__header {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #ef4444;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 6px;
}

.error-card__list {
    margin: 0;
    padding-left: 20px;
    color: rgba(255, 255, 255, 0.65);
    font-size: 12px;
    line-height: 1.6;
}

.delivery-rebook-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 12px;
    background: rgba(245, 158, 11, 0.1);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 10px;
    margin-top: 4px;
}

.btn-delivery-issue {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--color-warning);
    font-size: 12px;
    font-weight: 600;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    font-family: inherit;
    text-align: left;
}

.btn-rebook {
    background: rgba(245, 158, 11, 0.2);
    color: var(--color-warning);
    border: 1px solid rgba(245, 158, 11, 0.4);
    font-size: 12px;
    font-weight: 600;
    border-radius: 8px;
    padding: 4px 10px;
    flex-shrink: 0;
}

.rebook-admin-notice {
    font-size: 11px;
    color: #ef4444;
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 8px;
    padding: 6px 10px;
    margin-bottom: 6px;
    line-height: 1.5;
}

.order-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.order-actions-right {
    display: flex;
    gap: 8px;
}

.btn-contact {
    color: var(--text-secondary);
    font-size: 12px;
    border-radius: 8px;
    padding: 6px 10px;
}

.buyer-info-popup {
    background: #1f2940;
    border-radius: 12px;
    padding: 14px 16px;
    min-width: 220px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.buyer-info-row {
    font-size: 13px;
    color: var(--text-primary);
    line-height: 1.5;
}

.buyer-info-label {
    font-size: 11px;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 2px;
}

.buyer-info-value {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
}

.buyer-info-na {
    font-size: 12px;
    color: var(--text-muted);
    font-style: italic;
}

.btn-copy {
    background: none;
    border: none;
    padding: 2px;
    cursor: pointer;
    color: var(--text-muted);
    flex-shrink: 0;
    margin-top: 1px;

    &:hover {
        color: var(--text-primary);
    }
}

.btn-accept {
    background: var(--color-accent);
    color: #121b2f;
    font-weight: 600;
    font-size: 13px;
    padding: 8px 16px;
    border-radius: 10px;
}

.btn-reject {
    color: #ef4444;
    font-size: 13px;
    padding: 8px 12px;
    border-radius: 10px;
}

.reject-dialog {
    background: #1f2940;
    border-radius: 16px;
    min-width: 300px;
    color: var(--text-primary);
}

.dialog-title {
    font-size: 17px;
    font-weight: 700;
    margin-bottom: 4px;
}

.dialog-sub {
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 16px;
}

.reason-options {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;
}

.reason-chip {
    padding: 8px 14px;
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-primary);
    font-size: 13px;
    cursor: pointer;
    font-family: inherit;
}

.reason-chip.active {
    border-color: var(--color-accent);
    background: rgba(245, 166, 35, 0.15);
    color: var(--color-accent);
}

.custom-reason-input {
    margin-top: 8px;
}

.order-variant {
    color: #f5A623;
    font-weight: 600;
}
</style>
