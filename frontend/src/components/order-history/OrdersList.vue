<script>
import { mapState } from 'pinia';
import { useOrderStore } from '@/stores/order/orderStore';
import OrderCard from '@/components/order-history/OrderCard.vue';

export default {
    components: {
        OrderCard
    },

    data() {
        return {}
    },

    computed: {
        ...mapState(useOrderStore, ['orders', 'selectedFilter', 'loading']),

        filteredOrders() {
            if (this.selectedFilter === 'all') return this.orders
            if (this.selectedFilter === 'unpaid') {
                return this.orders.filter(o => o.payment_status === 'pending' && o.status !== 'cancelled')
            }
            if (this.selectedFilter === 'active') {
                return this.orders.filter(o => o.payment_status === 'paid' && ['pending', 'confirmed', 'ready', 'delivery_failed'].includes(o.status))
            }
            if (this.selectedFilter === 'completed') {
                return this.orders.filter(o => o.status === 'done')
            }
            if (this.selectedFilter === 'cancelled') {
                return this.orders.filter(o => o.status === 'cancelled')
            }
            return this.orders
        }
    },

    methods: {
        notifyStatusChange(newStatus, oldStatus) {
            if (newStatus === oldStatus) return
            const key = `orders_page.toast_${newStatus}`   // i18n, a neutral cancel line (T178 A43)
            if (!this.$te(key)) return
            const message = this.$t(key)

            const isCancelled = newStatus === 'cancelled'
            this.$q.notify({
                classes: isCancelled ? 'quasar-notify-negative' : 'quasar-notify-positive',
                message: `🔔 ${message}`,
                progress: true,
                position: 'bottom',
                timeout: 2500,
            })
        },
    },

    watch: {
        // Detect order status transitions on each poll → toast notification
        orders(newOrders, oldOrders) {
            if (!oldOrders || oldOrders.length === 0) return
            for (const newO of newOrders) {
                const oldO = oldOrders.find(o => o.id === newO.id)
                if (oldO && oldO.status !== newO.status) {
                    this.notifyStatusChange(newO.status, oldO.status)
                }
            }
        },
    },

    mounted() {
        const orderStore = useOrderStore()
        orderStore.getOrders()
        orderStore.startWatchingOrders()
    },

    beforeUnmount() {
        useOrderStore().stopWatchingOrders()
    }
}
</script>

<template>
    <div class="orders-list">

        <!-- Skeleton -->
        <template v-if="loading">
            <div v-for="n in 3" :key="n" class="skeleton-card">
                <div class="sk-top">
                    <q-skeleton type="rect" width="42px" height="42px" style="border-radius:12px;" animation="pulse" />
                    <div class="sk-info">
                        <q-skeleton type="text" width="120px" height="15px" animation="pulse" />
                        <q-skeleton type="text" width="80px" height="12px" animation="pulse" style="margin-top:6px;" />
                    </div>
                    <q-skeleton type="rect" width="72px" height="24px" style="border-radius:100px;" animation="pulse" />
                </div>
                <div class="sk-divider" />
                <div class="sk-bottom">
                    <q-skeleton type="text" width="100px" height="16px" animation="pulse" />
                    <q-skeleton type="text" width="70px" height="14px" animation="pulse" />
                </div>
            </div>
        </template>

        <!-- Empty state -->
        <div v-else-if="filteredOrders.length === 0" class="empty-state">
            <div class="empty-icon">🛍️</div>
            <div class="empty-title">{{ $t('orders_page.empty_title') }}</div>
            <div class="empty-subtitle">{{ $t('orders_page.empty_subtitle') }}</div>
        </div>

        <!-- List -->
        <template v-else>
            <OrderCard
                v-for="order in filteredOrders"
                :key="order.id"
                :order="order"
            />
        </template>

    </div>
</template>

<style lang="scss" scoped>
.orders-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-top: 12px;
}

/* Skeleton card mirrors OrderCard layout */
.skeleton-card {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 1rem;
    padding: 16px;
}

.sk-top {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
}

.sk-info {
    flex: 1;
}

.sk-divider {
    height: 1px;
    background: rgba(255, 255, 255, 0.06);
    margin: 0 -16px;
}

.sk-bottom {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 12px;
}

/* Empty state */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 60px 20px;
    gap: 10px;
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
