<script>
import { Wallet, ChevronRight } from 'lucide-vue-next';
import { mapState, mapActions } from 'pinia';
import SectionTitle from '@/components/shared/SectionTitle.vue';
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import { formatVnTime } from '@/utils/vnTime';
import { formatVnd } from '@/utils/priceDisplay';
import { orderCode } from '@/utils/orderCode';
import { SUPPORT_EMAIL, SUPPORT_MAILTO } from '@/utils/support';

const STATE_DOT = {
    pending:    'dot-pending',
    processing: 'dot-processing',
    paid_out:   'dot-paid',
    held:       'dot-held',
}

const PAYOUT_STATE = {   // admin_payouts.status → the order-level wording
    pending:    'pending',
    processing: 'processing',
    completed:  'paid_out',
    failed:     'failed',
}

const PREVIEW_PAYOUTS = 2   // UI constant, like the review preview: the Me page shows the newest 2 payouts

export default {
    name: 'SellerMeEarnings',

    components: { Wallet, ChevronRight, SectionTitle },

    // preview > 0: the Me page shows the newest `preview` orders + 2 payouts and a link to
    // /seller/me/earnings. 0: everything, orders by month and payouts in two tabs.
    props: {
        preview: { type: Number, default: 0 },
    },

    data() {
        return {
            loading: true,
            error: false,
            tab: 'orders',
            openId: null,       // order whose split is shown
            supportEmail: SUPPORT_EMAIL,
            supportMailto: SUPPORT_MAILTO,
        }
    },

    computed: {
        ...mapState(useDashboardStore, { data: 'earnings' }),

        isEmpty() {
            return !this.data?.orders?.length && !this.data?.payouts?.length
        },

        // API order: newest first (orders by done time, payouts by period end)
        orders() {
            const list = this.data?.orders || []
            return (this.preview ? list.slice(0, this.preview) : list).map(o => ({
                ...o,
                code: orderCode(o.id),
                doneText: this.day(o.done_at),
                month: formatVnTime(o.done_at, { month: 'long', year: 'numeric' }),
                fees: (o.commission_amount || 0) + (o.vat_amount || 0),   // whole VND from the API
                dotClass: STATE_DOT[o.payout_state] || 'dot-held',
                stateText: o.payout_state === 'pending' && o.expected_payout_date
                    ? this.$t('seller_me.earnings_state_pending_on', { date: this.day(o.expected_payout_date) })
                    : this.$t(`seller_me.earnings_state_${o.payout_state}`),
            }))
        },

        // [{ month, orders }] in Vietnam time, newest month first
        months() {
            const groups = []
            for (const o of this.orders) {
                if (groups.at(-1)?.month !== o.month) groups.push({ month: o.month, orders: [] })
                groups.at(-1).orders.push(o)
            }
            return groups
        },

        payouts() {
            const list = this.data?.payouts || []
            return (this.preview ? list.slice(0, PREVIEW_PAYOUTS) : list).map(p => {
                const state = PAYOUT_STATE[p.status] || p.status
                return {
                    ...p,
                    periodText: p.period_start === p.period_end
                        ? this.day(p.period_end)
                        : `${this.day(p.period_start)} – ${this.day(p.period_end)}`,
                    dotClass: STATE_DOT[state] || 'dot-held',
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
        ...mapActions(useDashboardStore, ['fetchEarnings']),

        async load() {
            this.loading = !this.data   // shown again at once when coming back; refreshed underneath
            this.error = false
            try {
                await this.fetchEarnings()
            } catch (e) {
                console.error('SellerMeEarnings - load -', e)
                this.error = !this.data
            } finally {
                this.loading = false
            }
        },

        formatVnd,

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
    <div class="earnings">
        <SectionTitle v-if="preview">{{ $t('seller_me.section_title_earnings') }}</SectionTitle>

        <div v-if="loading" class="card card--pad">
            <q-skeleton type="rect" height="56px" style="border-radius:12px;" animation="pulse" />
            <q-skeleton type="text" width="80%" animation="pulse" />
            <q-skeleton type="text" width="60%" animation="pulse" />
        </div>

        <div v-else-if="error" class="card card--pad state">
            <div class="state-text">{{ $t('seller_me.earnings_load_error') }}</div>
            <q-btn flat no-caps dense class="link-btn" :label="$t('seller_me.earnings_retry')" @click="load" />
        </div>

        <div v-else-if="isEmpty" class="card card--pad state">
            <Wallet :size="28" class="state-icon" />
            <div class="state-text">{{ $t('seller_me.earnings_empty') }}</div>
            <div class="state-sub">{{ $t('seller_me.earnings_empty_sub') }}</div>
            <div class="state-links">
                <a href="/docs/sariko_fees.html" target="_blank">{{ $t('seller_me.menu_label_fees') }}</a>
                <a :href="supportMailto">{{ supportEmail }}</a>
            </div>
        </div>

        <template v-else>
            <div class="card">
                <div class="row">
                    <span class="main kpi-label">{{ $t('seller_me.earnings_awaiting') }}</span>
                    <span class="money kpi-value kpi-value--awaiting">{{ formatVnd(data.awaiting_total) }}</span>
                </div>
                <div class="row">
                    <span class="main kpi-label">{{ $t('seller_me.earnings_received', { n: data.payouts_limit }) }}</span>
                    <span class="money kpi-value kpi-value--paid">{{ formatVnd(data.received_total) }}</span>
                </div>
            </div>

            <!-- Me page: newest orders + payouts, link to the full page -->
            <template v-if="preview">
                <template v-if="orders.length">
                    <SectionTitle class="gap">{{ $t('seller_me.earnings_latest_orders') }}</SectionTitle>
                    <div class="card">
                        <div v-for="o in orders" :key="o.id" class="row">
                            <div class="main">
                                <div class="row-title">{{ o.code }} · {{ o.doneText }}</div>
                                <div class="status"><i :class="o.dotClass" />{{ o.stateText }}</div>
                            </div>
                            <span class="money">{{ formatVnd(o.payout_amount) }}</span>
                        </div>
                        <router-link v-if="!payouts.length" to="/seller/me/earnings" class="see-all">
                            {{ $t('seller_me.earnings_see_all') }} <ChevronRight :size="16" />
                        </router-link>
                    </div>
                </template>

                <template v-if="payouts.length">
                    <SectionTitle class="gap">{{ $t('seller_me.earnings_latest_payouts') }}</SectionTitle>
                    <div class="card">
                        <div v-for="p in payouts" :key="p.id" class="row">
                            <div class="main">
                                <div class="row-title">{{ p.periodText }}</div>
                                <div class="status"><i :class="p.dotClass" />{{ p.stateText }}<template v-if="p.paidText"> · {{ p.paidText }}</template></div>
                            </div>
                            <span class="money">{{ formatVnd(p.net_payout) }}</span>
                        </div>
                        <router-link to="/seller/me/earnings" class="see-all">
                            {{ $t('seller_me.earnings_see_all') }} <ChevronRight :size="16" />
                        </router-link>
                    </div>
                </template>
            </template>

            <!-- Earnings page: every order (by month) and every payout -->
            <template v-else>
                <q-btn-toggle
                    v-model="tab"
                    spread no-caps unelevated
                    color="transparent" text-color="grey-5" toggle-color="grey-9" toggle-text-color="white"
                    class="seg"
                    :options="[
                        { label: $t('seller_me.earnings_tab_orders', { days: data.history_days }), value: 'orders' },
                        { label: $t('seller_me.earnings_payouts_title'), value: 'payouts' },
                    ]"
                />

                <template v-if="tab === 'orders'">
                    <div v-if="!orders.length" class="empty-tab">{{ $t('seller_me.earnings_empty') }}</div>
                    <template v-for="g in months" :key="g.month">
                        <SectionTitle class="gap">{{ g.month }}</SectionTitle>
                        <div class="card">
                            <div v-for="o in g.orders" :key="o.id" class="row row--tap" @click="openId = openId === o.id ? null : o.id">
                                <div class="main">
                                    <div class="row-title">{{ o.code }} · {{ o.doneText }}</div>
                                    <div class="row-sub">{{ $t('seller_me.earnings_fees', { food: formatVnd(o.subtotal), fees: formatVnd(o.fees) }) }}</div>
                                    <div class="status"><i :class="o.dotClass" />{{ o.stateText }}</div>
                                    <div v-if="openId === o.id" class="detail">
                                        <div>{{ $t('seller_me.earnings_split', { food: formatVnd(o.subtotal), commission: formatVnd(o.commission_amount), vat: formatVnd(o.vat_amount) }) }}</div>
                                        <div v-if="o.wh_vat_amount || o.wh_pit_amount">{{ $t('seller_me.earnings_withholding', { vat: formatVnd(o.wh_vat_amount), pit: formatVnd(o.wh_pit_amount) }) }}</div>
                                    </div>
                                </div>
                                <span class="money">{{ formatVnd(o.payout_amount) }}</span>
                                <ChevronRight :size="16" class="chev" :class="{ open: openId === o.id }" />
                            </div>
                        </div>
                    </template>
                </template>

                <template v-else>
                    <div v-if="!payouts.length" class="empty-tab">{{ $t('seller_me.earnings_empty') }}</div>
                    <div v-else class="card gap">
                        <div v-for="p in payouts" :key="p.id" class="row">
                            <div class="main">
                                <div class="row-title">{{ p.periodText }}</div>
                                <div v-if="p.withholding_amount" class="row-sub">{{ $t('seller_me.earnings_payout_withholding', { amount: formatVnd(p.withholding_amount) }) }}</div>
                                <div v-if="p.total_deductions" class="row-sub">{{ $t('seller_me.earnings_deductions', { amount: formatVnd(p.total_deductions) }) }}</div>
                                <div class="status"><i :class="p.dotClass" />{{ p.stateText }}<template v-if="p.paidText"> · {{ p.paidText }}</template></div>
                            </div>
                            <span class="money">{{ formatVnd(p.net_payout) }}</span>
                        </div>
                    </div>
                </template>

                <div class="note">
                    {{ $t('seller_me.earnings_note') }}
                    <a href="/docs/sariko_fees.html" target="_blank">{{ $t('seller_me.menu_label_fees') }}</a>
                </div>
            </template>
        </template>
    </div>
</template>

<style scoped>
/* "Grouped list" like Settings: one surface per section, hairline dividers, 8px rhythm */
.card {
    background: rgb(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
}

.card--pad {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.gap {
    margin-top: 24px;
}

.row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 16px;
    min-height: 52px;
}

.row + .row {
    border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.row--tap {
    cursor: pointer;
}

.main {
    flex: 1;
    min-width: 0;
}

.row-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

.row-sub {
    margin-top: 2px;
    font-size: 12px;
    color: var(--text-secondary);
}

.money {
    flex-shrink: 0;
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
    text-align: right;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
}

.kpi-label {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-secondary);
}

.kpi-value {
    font-size: 20px;
    font-weight: 800;
}

.kpi-value--awaiting { color: var(--color-warning); }
.kpi-value--paid     { color: var(--color-success); }

.status {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 4px;
    font-size: 12px;
    color: var(--text-secondary);
}

.status i {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
}

.dot-pending    { background: var(--color-warning); }
.dot-processing { background: var(--color-info); }
.dot-paid       { background: var(--color-success); }
.dot-held       { background: var(--color-error); }

.detail {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 12px;
    color: var(--text-secondary);
}

.chev {
    flex-shrink: 0;
    color: var(--text-muted);
    transition: transform 0.15s ease;
}

.chev.open {
    transform: rotate(90deg);
}

.see-all {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 14px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    color: var(--color-accent);
    font-size: 14px;
    font-weight: 700;
    text-decoration: none;
}

.seg {
    margin-top: 16px;
    padding: 4px;
    border-radius: 12px;
    background: rgb(255, 255, 255, 0.08);
    font-weight: 700;
}

.seg :deep(.q-btn) {
    border-radius: 9px;
}

.empty-tab {
    margin-top: 24px;
    text-align: center;
    font-size: 13px;
    color: var(--text-secondary);
}

.state {
    align-items: center;
    gap: 6px;
    text-align: center;
}

.state-icon {
    color: var(--color-accent);
    opacity: 0.6;
    margin-bottom: 4px;
}

.state-text {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
}

.state-sub {
    font-size: 13px;
    color: var(--text-secondary);
}

.state-links {
    display: flex;
    gap: 16px;
    margin-top: 4px;
    font-size: 13px;
}

.state-links a,
.note a {
    color: var(--color-accent);
}

.link-btn {
    color: var(--color-accent);
    font-weight: 600;
}

.note {
    margin-top: 16px;
    font-size: 12px;
    color: var(--text-muted);
}
</style>
