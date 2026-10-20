<script>
import { mapState, mapActions } from 'pinia';
import { Search } from 'lucide-vue-next';
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import apiSellerDashboard from '@/apis/sellers/apiSellerDashboard';
import { liveDeliveryKey } from '@/utils/deliveryBadge';
import { formatVnTime, vnDay } from '@/utils/vnTime';
import { orderCode } from '@/utils/orderCode';

const SEARCH_MIN_LENGTH = 2   // the API rejects shorter terms
const SEARCH_DEBOUNCE_MS = 300

const FILTER_KEYS = ['all', 'new', 'preparing', 'ready', 'delivery_failed', 'done', 'cancelled']

const STATUS_DISPLAY_KEY = {
    pending:          'seller_orders.status_new',
    confirmed:        'seller_orders.status_preparing',
    ready:            'seller_orders.status_ready',
    done:             'seller_orders.status_done',
    cancelled:        'seller_orders.status_cancelled',
    delivery_failed:  'seller_orders.status_delivery_failed',
}

const STATUS_CLASS = {
    pending:          'badge-new',
    confirmed:        'badge-preparing',
    ready:            'badge-ready',
    done:             'badge-done',
    cancelled:        'badge-cancelled',
    delivery_failed:  'badge-delivery-failed',
}

export default {
    name: 'SellerOrdersList',

    components: { Search },

    data() {
        return {
            activeFilter: 'all',
            searchTerm: '',
            searchResults: [],
            searchLoading: false,
        }
    },

    computed: {
        ...mapState(useDashboardStore, ['isLoading', 'historyDays']),

        isSearching() {
            return this.searchTerm.trim().length >= SEARCH_MIN_LENGTH
        },

        // Search results (any age) replace the list; the filter chips apply to either.
        orders() {
            return this.isSearching ? this.searchResults : useDashboardStore().orders
        },

        filters() {
            return FILTER_KEYS.map(key => ({
                key,
                label: this.$t(`seller_orders.filter_${key}`),
            }))
        },

        filterCounts() {
            const o = this.orders
            return {
                all:              o.length,
                new:              o.filter(x => x.status === 'pending').length,
                preparing:        o.filter(x => x.status === 'confirmed').length,
                ready:            o.filter(x => x.status === 'ready').length,
                delivery_failed:  o.filter(x => x.status === 'delivery_failed').length,
                done:             o.filter(x => x.status === 'done').length,
                cancelled:        o.filter(x => x.status === 'cancelled').length,
            }
        },

        filteredOrders() {
            const f = this.activeFilter
            if (f === 'all')              return this.orders
            if (f === 'new')              return this.orders.filter(o => o.status === 'pending')
            if (f === 'preparing')        return this.orders.filter(o => o.status === 'confirmed')
            if (f === 'ready')            return this.orders.filter(o => o.status === 'ready')
            if (f === 'delivery_failed')  return this.orders.filter(o => o.status === 'delivery_failed')
            if (f === 'done')             return this.orders.filter(o => o.status === 'done')
            if (f === 'cancelled')        return this.orders.filter(o => o.status === 'cancelled')
            return this.orders
        },

        groupedOrders() {
            const today = vnDay(new Date())
            const yesterday = vnDay(new Date(Date.now() - 86400000))
            const groups = {}

            for (const order of this.filteredOrders) {
                const d = vnDay(order.created_at)
                let label
                if (d === today)          label = this.$t('seller_orders.group_today')
                else if (d === yesterday) label = this.$t('seller_orders.group_yesterday')
                else label = formatVnTime(order.created_at, { day: '2-digit', month: '2-digit', year: 'numeric' })

                if (!groups[label]) groups[label] = []
                groups[label].push({
                    ...order,
                    displayStatus: this.$t(liveDeliveryKey(order) || STATUS_DISPLAY_KEY[order.status] || order.status),
                    statusClass:   STATUS_CLASS[order.status] || '',
                    code:          orderCode(order.id),
                    customerName:  order.users?.name || order.users?.email || this.$t('seller_orders.customer_fallback'),
                    itemCount:     (order.order_items || []).length,
                    totalText:     new Intl.NumberFormat('vi-VN').format(order.total_amount || 0) + ' ₫',
                    timeText:      formatVnTime(order.created_at, { hour: '2-digit', minute: '2-digit' }),
                    appointmentText: order.delivery_appointment
                        ? formatVnTime(order.delivery_appointment, { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
                        : null,
                })
            }

            return Object.entries(groups)
        },
    },

    watch: {
        searchTerm() {
            clearTimeout(this._searchTimer)
            if (!this.isSearching) {
                this.searchResults = []
                this.searchLoading = false
                return
            }
            this.searchLoading = true
            this._searchTimer = setTimeout(this.runSearch, SEARCH_DEBOUNCE_MS)
        },
    },

    methods: {
        ...mapActions(useDashboardStore, ['fetchOrders', 'startWatchingOrders', 'stopWatchingOrders']),

        async runSearch() {
            const term = this.searchTerm.trim()
            try {
                const res = await apiSellerDashboard.searchOrders(term)
                if (term === this.searchTerm.trim()) this.searchResults = res.orders || []
            } catch (e) {
                console.error('SellerOrdersList - runSearch -', e)
                if (term === this.searchTerm.trim()) this.searchResults = []
            } finally {
                if (term === this.searchTerm.trim()) this.searchLoading = false
            }
        },

        goToDetail(orderId) {
            this.$router.push({ name: 'seller-order-detail', params: { orderId } })
        },
    },

    async mounted() {
        await this.fetchOrders()
        // Keep badges live (incl. Lalamove steps); refcounted with the seller home page
        this.startWatchingOrders()
    },

    beforeUnmount() {
        clearTimeout(this._searchTimer)
        this.stopWatchingOrders()
    },
}
</script>

<template>
    <div>
        <!-- Search -->
        <div class="search-box">
            <Search :size="16" class="search-icon" />
            <input
                v-model="searchTerm"
                type="search"
                class="search-input"
                :placeholder="$t('seller_orders.search_placeholder')"
            />
        </div>

        <!-- Filter chips -->
        <div class="filter-scroll">
            <button
                v-for="f in filters"
                :key="f.key"
                class="filter-chip"
                :class="{ active: activeFilter === f.key }"
                @click="activeFilter = f.key"
            >
                {{ f.label }}
                <span v-if="filterCounts[f.key] > 0" class="chip-count">{{ filterCounts[f.key] }}</span>
            </button>
        </div>

        <!-- Loading -->
        <div v-if="isLoading || (isSearching && searchLoading)" class="skeleton-list">
            <div v-for="n in 4" :key="n" class="sk-card">
                <div class="sk-row">
                    <div class="sk-left">
                        <q-skeleton type="text" width="130px" height="15px" animation="pulse" />
                        <q-skeleton type="text" width="100px" height="13px" animation="pulse" style="margin-top:6px;" />
                    </div>
                    <div class="sk-right">
                        <q-skeleton type="rect" width="72px" height="22px" style="border-radius:12px;" animation="pulse" />
                        <q-skeleton type="text" width="36px" height="11px" animation="pulse" style="margin-top:6px;" />
                    </div>
                </div>
            </div>
        </div>

        <!-- Empty -->
        <div v-else-if="filteredOrders.length === 0" class="empty-state">
            <div class="empty-icon">🧾</div>
            <template v-if="isSearching">
                <div class="empty-title">{{ $t('seller_orders.search_empty') }}</div>
                <div class="empty-subtitle">{{ $t('seller_orders.search_empty_subtitle') }}</div>
            </template>
            <template v-else>
                <div class="empty-title">{{ $t('seller_orders.empty') }}</div>
                <div class="empty-subtitle">{{ $t('seller_orders.empty_subtitle') }}</div>
            </template>
        </div>

        <!-- Grouped list -->
        <div v-else class="groups">
            <div v-for="[label, group] in groupedOrders" :key="label" class="date-group">
                <div class="date-label">{{ label }}</div>
                <div
                    v-for="order in group"
                    :key="order.id"
                    class="order-card"
                    @click="goToDetail(order.id)"
                >
                    <div class="order-row">
                        <div class="order-info">
                            <div class="customer-name">{{ order.customerName }} <span class="order-code">{{ order.code }}</span></div>
                            <div class="order-meta">{{ $t('seller_orders.item_count', order.itemCount, { count: order.itemCount }) }} · {{ order.totalText }}</div>
                            <div v-if="order.appointmentText" class="appointment-text">📅 {{ order.appointmentText }}</div>
                        </div>
                        <div class="order-right">
                            <span class="status-badge" :class="order.statusClass">{{ order.displayStatus }}</span>
                            <div class="order-time">{{ order.timeText }}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div v-if="!isSearching && !isLoading && historyDays" class="history-note">
            {{ $t('seller_orders.history_note', { days: historyDays }, historyDays) }}
        </div>
    </div>
</template>

<style lang="scss" scoped>
.search-box {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 16px 16px 0;
    padding: 0 14px;
    height: 42px;
    border-radius: 21px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.05);
}

.search-icon {
    flex-shrink: 0;
    color: var(--text-muted);
}

.search-input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    color: var(--text-primary);
    font-size: 14px;
    font-family: inherit;
    &::placeholder { color: var(--text-muted); }
}

.history-note {
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    padding: 16px 8px 8px;
}

.filter-scroll {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding: 16px;
    scrollbar-width: none;
    &::-webkit-scrollbar { display: none; }
}

.filter-chip {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 7px 14px;
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: transparent;
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s;

    &.active {
        background: var(--color-accent);
        border-color: var(--color-accent);
        color: #121b2f;
        font-weight: 700;
    }
}

.chip-count {
    background: rgba(0, 0, 0, 0.15);
    border-radius: 10px;
    padding: 1px 6px;
    font-size: 11px;
}

.skeleton-list, .groups {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.date-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.date-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 4px 0;
}

.order-card {
    background: rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    padding: 14px 16px;
    cursor: pointer;
    transition: background 0.15s;
    &:active { background: rgba(255, 255, 255, 0.12); }
}

.order-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
}

.customer-name {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.order-code {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
}

.order-meta {
    font-size: 13px;
    color: var(--text-secondary);
}

.appointment-text {
    font-size: 11px;
    font-weight: 600;
    color: var(--color-accent);
    margin-top: 2px;
}

.order-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
    flex-shrink: 0;
}

.order-time {
    font-size: 11px;
    color: var(--text-muted);
}

.status-badge {
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 12px;
}

.badge-new             { background: rgba(245,158,11,0.15); color: var(--color-warning); }
.badge-preparing       { background: rgba(59,130,246,0.15);  color: var(--color-info); }
.badge-ready           { background: rgba(139,92,246,0.15);  color: #a78bfa; }
.badge-done            { background: rgba(34,197,94,0.15);   color: var(--color-success); }
.badge-cancelled       { background: rgba(239,68,68,0.1);    color: #ef4444; }
.badge-delivery-failed { background: rgba(245,158,11,0.15);  color: #f59e0b; }

/* Skeleton */
.sk-card {
    background: rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    padding: 14px 16px;
}

.sk-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
}

.sk-left { flex: 1; }

.sk-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    flex-shrink: 0;
}

/* Empty state */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 60px 20px;
    gap: 8px;
}

.empty-icon {
    font-size: 48px;
    margin-bottom: 4px;
}

.empty-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
}

.empty-subtitle {
    font-size: 13px;
    color: var(--text-muted);
    text-align: center;
}
</style>
