<script>
import { mapState } from 'pinia';
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import { vnDay } from '@/utils/vnTime';

export default {
    name: 'SellerStatsGrid',

    computed: {
        ...mapState(useDashboardStore, ['orders']),

        // Done and food sales count orders finished today (Vietnam time); New / Preparing are the live queue.
        todayOrders() {
            const today = vnDay(new Date())
            return this.orders.filter(o => o.status_changed_at && vnDay(o.status_changed_at) === today)
        },

        stats() {
            const doneOrders = this.todayOrders.filter(o => o.status === 'done')
            // Food sales: dish prices only (no delivery fee, before Sariko fees); whole VND integers.
            const salesTotal = doneOrders.reduce((sum, o) =>
                sum + (o.order_items || []).reduce((s, i) => s + i.price_snapshot * i.quantity, 0), 0)

            // Sales first, full row; the three counts share the row below.
            return [
                { key: 'sales', isSales: true, label: this.$t('seller_home.stat_label_sales'), value: new Intl.NumberFormat('vi-VN').format(salesTotal) + ' ₫' },
                { key: 'new',   label: this.$t('seller_home.stat_label_new'),       value: this.orders.filter(o => o.status === 'pending').length },
                { key: 'prep',  label: this.$t('seller_home.stat_label_preparing'), value: this.orders.filter(o => o.status === 'confirmed').length },
                { key: 'done',  label: this.$t('seller_home.stat_label_done'),      value: doneOrders.length },
            ]
        },
    },
}
</script>

<template>
    <div class="stats-grid">
        <div
            v-for="stat in stats"
            :key="stat.key"
            class="stat-card"
            :class="{ 'stat-card--sales': stat.isSales }"
        >
            <span class="stat-label" :title="stat.label">{{ stat.label }}</span>
            <div class="stat-value">{{ stat.value }}</div>
        </div>
    </div>
</template>

<style lang="scss" scoped>
// Neutral cards like the admin dashboard on phones: one-line label, the number shrinks with the screen.
.stats-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    font-family: $sariko-font-family-secondary;
}

.stat-card {
    background-color: var(--bg-surface-2);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
}

.stat-card--sales { grid-column: 1 / -1; }

.stat-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.stat-value {
    font-size: clamp(18px, 6vw, 24px);
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
}

.stat-card--sales .stat-value { font-size: clamp(22px, 8vw, 28px); }
</style>
