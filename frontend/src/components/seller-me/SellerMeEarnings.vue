<script>
import { Wallet } from 'lucide-vue-next';
import apiSellerDashboard from '@/apis/sellers/apiSellerDashboard';
import { formatVnTime } from '@/utils/vnTime';
import { orderCode } from '@/utils/orderCode';
import { SUPPORT_EMAIL, SUPPORT_MAILTO } from '@/utils/support';

const STATE_CLASS = {
    pending:    'chip-pending',
    processing: 'chip-processing',
    paid_out:   'chip-paid',
    held:       'chip-held',
}

const PAYOUT_STATE = {   // admin_payouts.status → the order-level wording
    pending:    'pending',
    processing: 'processing',
    completed:  'paid_out',
    failed:     'failed',
}

export default {
    name: 'SellerMeEarnings',

    components: { Wallet },

    data() {
        return {
            data: null,
            loading: true,
            error: false,
            supportEmail: SUPPORT_EMAIL,
            supportMailto: SUPPORT_MAILTO,
        }
    },

    computed: {
        isEmpty() {
            return !this.data?.orders?.length && !this.data?.payouts?.length
        },

        orders() {
            return (this.data?.orders || []).map(o => ({
                ...o,
                code: orderCode(o.id),
                doneText: this.day(o.done_at),
                stateClass: STATE_CLASS[o.payout_state] || '',
                stateText: o.payout_state === 'pending' && o.expected_payout_date
                    ? this.$t('seller_me.earnings_state_pending_on', { date: this.day(o.expected_payout_date) })
                    : this.$t(`seller_me.earnings_state_${o.payout_state}`),
            }))
        },

        payouts() {
            return (this.data?.payouts || []).map(p => {
                const state = PAYOUT_STATE[p.status] || p.status
                return {
                    ...p,
                    periodText: p.period_start === p.period_end
                        ? this.day(p.period_end)
                        : `${this.day(p.period_start)} – ${this.day(p.period_end)}`,
                    stateClass: STATE_CLASS[state] || 'chip-held',
                    stateText: this.$t(`seller_me.earnings_state_${state}`),
                    paidText: p.paid_at ? this.day(p.paid_at) : null,
                }
            })
        },
    },

    mounted() {
        this.load()
    },

    methods: {
        async load() {
            this.loading = true
            this.error = false
            try {
                this.data = await apiSellerDashboard.getEarnings()
            } catch (e) {
                console.error('SellerMeEarnings - load -', e)
                this.error = true
            } finally {
                this.loading = false
            }
        },

        vnd(amount) {
            return new Intl.NumberFormat('vi-VN').format(amount || 0) + ' ₫'
        },

        // "2026-10-23" (a plain date) or a timestamp → the day in Vietnam time. With the
        // year: vi-VN writes day + month alone as "23-10".
        day(value) {
            if (!value) return ''
            const v = /^\d{4}-\d{2}-\d{2}$/.test(value) ? value + 'T12:00:00+07:00' : value
            return formatVnTime(v, { day: '2-digit', month: '2-digit', year: 'numeric' })
        },
    },
}
</script>

<template>
    <div>
        <div class="section-title">{{ $t('seller_me.section_title_earnings') }}</div>
        <div class="earnings-card">

            <template v-if="loading">
                <q-skeleton type="rect" height="56px" style="border-radius:12px;" animation="pulse" />
                <q-skeleton type="text" width="80%" animation="pulse" />
                <q-skeleton type="text" width="60%" animation="pulse" />
            </template>

            <div v-else-if="error" class="earnings-state">
                <div class="earnings-state-text">{{ $t('seller_me.earnings_load_error') }}</div>
                <q-btn flat no-caps dense class="earnings-btn" :label="$t('seller_me.earnings_retry')" @click="load" />
            </div>

            <div v-else-if="isEmpty" class="earnings-state">
                <Wallet :size="28" class="earnings-icon" />
                <div class="earnings-state-text">{{ $t('seller_me.earnings_empty') }}</div>
                <div class="earnings-state-sub">{{ $t('seller_me.earnings_empty_sub', { days: data.payout_delay_days }) }}</div>
                <div class="earnings-links">
                    <a href="/docs/sariko_fees.html" target="_blank">{{ $t('seller_me.menu_label_fees') }}</a>
                    <a :href="supportMailto">{{ supportEmail }}</a>
                </div>
            </div>

            <template v-else>
                <div class="totals">
                    <div class="total">
                        <div class="total-label">{{ $t('seller_me.earnings_awaiting') }}</div>
                        <div class="total-value">{{ vnd(data.awaiting_total) }}</div>
                    </div>
                    <div class="total">
                        <div class="total-label">{{ $t('seller_me.earnings_received', { n: data.payouts_limit }) }}</div>
                        <div class="total-value total-value--paid">{{ vnd(data.received_total) }}</div>
                    </div>
                </div>

                <div v-if="orders.length" class="block">
                    <div class="block-title">{{ $t('seller_me.earnings_orders_title', { days: data.history_days }) }}</div>
                    <div v-for="o in orders" :key="o.id" class="row">
                        <div class="row-head">
                            <span class="row-code">{{ o.code }} · {{ o.doneText }}</span>
                            <span class="row-amount">{{ vnd(o.payout_amount) }}</span>
                        </div>
                        <div class="row-split">
                            {{ $t('seller_me.earnings_split', {
                                food: vnd(o.subtotal), commission: vnd(o.commission_amount), vat: vnd(o.vat_amount),
                            }) }}
                        </div>
                        <div v-if="o.wh_vat_amount || o.wh_pit_amount" class="row-split">
                            {{ $t('seller_me.earnings_withholding', { vat: vnd(o.wh_vat_amount), pit: vnd(o.wh_pit_amount) }) }}
                        </div>
                        <span class="chip" :class="o.stateClass">{{ o.stateText }}</span>
                    </div>
                </div>

                <div v-if="payouts.length" class="block">
                    <div class="block-title">{{ $t('seller_me.earnings_payouts_title') }}</div>
                    <div v-for="p in payouts" :key="p.id" class="row">
                        <div class="row-head">
                            <span class="row-code">{{ p.periodText }}</span>
                            <span class="row-amount">{{ vnd(p.net_payout) }}</span>
                        </div>
                        <div v-if="p.withholding_amount" class="row-split">
                            {{ $t('seller_me.earnings_payout_withholding', { amount: vnd(p.withholding_amount) }) }}
                        </div>
                        <div v-if="p.total_deductions" class="row-split">
                            {{ $t('seller_me.earnings_deductions', { amount: vnd(p.total_deductions) }) }}
                        </div>
                        <span class="chip" :class="p.stateClass">
                            {{ p.stateText }}<template v-if="p.paidText"> · {{ p.paidText }}</template>
                        </span>
                    </div>
                </div>

                <div class="earnings-note">
                    {{ $t('seller_me.earnings_note', { days: data.payout_delay_days }) }}
                    <a href="/docs/sariko_fees.html" target="_blank">{{ $t('seller_me.menu_label_fees') }}</a>
                </div>
            </template>

        </div>
    </div>
</template>

<style scoped>
.section-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
    padding-left: 4px;
}

.earnings-card {
    background: rgb(255, 255, 255, 0.05);
    border-radius: 16px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}

.earnings-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 8px 0;
    text-align: center;
}

.earnings-icon {
    color: var(--color-accent);
    opacity: 0.6;
    margin-bottom: 4px;
}

.earnings-state-text {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
}

.earnings-state-sub {
    font-size: 13px;
    color: var(--text-secondary);
}

.earnings-links {
    display: flex;
    gap: 16px;
    margin-top: 4px;
    font-size: 13px;
}

.earnings-links a,
.earnings-note a {
    color: var(--color-accent);
}

.earnings-btn {
    align-self: center;
    color: var(--color-accent);
    font-weight: 600;
}

.totals {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}

.total {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 10px 12px;
    min-width: 0;
}

.total-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

.total-value {
    margin-top: 4px;
    font-size: 17px;
    font-weight: 700;
    color: var(--text-primary);
    overflow-wrap: anywhere;
}

.total-value--paid {
    color: var(--color-success);
}

.block {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.block-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

.row {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.row:last-child {
    padding-bottom: 0;
    border-bottom: none;
}

.row-head {
    align-self: stretch;
    display: flex;
    justify-content: space-between;
    gap: 10px;
}

.row-code {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
}

.row-amount {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
    flex-shrink: 0;
}

.row-split {
    font-size: 12px;
    color: var(--text-secondary);
}

.chip {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
}

.chip-pending    { background: rgba(245, 158, 11, 0.15); color: var(--color-warning); }
.chip-processing { background: rgba(59, 130, 246, 0.15); color: var(--color-info); }
.chip-paid       { background: rgba(34, 197, 94, 0.15);  color: var(--color-success); }
.chip-held       { background: rgba(239, 68, 68, 0.1);   color: #ef4444; }

.earnings-note {
    font-size: 12px;
    color: var(--text-muted);
}
</style>
