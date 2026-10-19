<script>
import { mapActions, mapState } from 'pinia';
import { BellRing } from 'lucide-vue-next';
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import { useAccountV2Store } from '@/stores/v2/account/accountStore';
import LayoutSellerHome from '@/layouts/seller/LayoutSellerHome.vue';
import SellerGreeting from '@/components/seller-home/SellerGreeting.vue';
import SellerStatsGrid from '@/components/seller-home/SellerStatsGrid.vue';
import ActionOrdersList from '@/components/seller-home/ActionOrdersList.vue';

export default {
    name: 'SellerHomePage',

    components: { LayoutSellerHome, SellerGreeting, SellerStatsGrid, ActionOrdersList, BellRing },

    data() {
        return {
            activeFilter: 'all',
        }
    },

    computed: {
        ...mapState(useAccountV2Store, ['notifications']),

        allActionOrders() {
            return useDashboardStore().orders.filter(o =>
                o.status === 'pending' ||
                o.status === 'confirmed' ||
                o.status === 'delivery_failed'
            )
        },

        filteredActionOrders() {
            if (this.activeFilter === 'pending')   return this.allActionOrders.filter(o => o.status === 'pending')
            if (this.activeFilter === 'confirmed') return this.allActionOrders.filter(o => o.status === 'confirmed')
            return this.allActionOrders
        },

        filterOptions() {
            return [
                { key: 'all',       label: this.$t('seller_orders.filter_all'),     count: this.allActionOrders.length },
                { key: 'pending',   label: this.$t('seller_orders.filter_new'),     count: this.allActionOrders.filter(o => o.status === 'pending').length },
                { key: 'confirmed', label: this.$t('seller_home.status_preparing'), count: this.allActionOrders.filter(o => o.status === 'confirmed').length },
            ]
        },

        activeFilterLabel() {
            return this.filterOptions.find(f => f.key === this.activeFilter)?.label || this.$t('seller_orders.filter_all')
        },

        actionDisplayCount() {
            return useDashboardStore().actionDisplayCount
        },
        isLoading() {
            return useDashboardStore().isLoading
        },
        showSkeleton() {
            const s = useDashboardStore()
            return s.isLoading && !s.hasLoadedOrders
        },
    },

    methods: {
        ...mapActions(useDashboardStore, ['fetchOrders', 'fetchSellerInfo', 'startWatchingOrders', 'stopWatchingOrders']),
        ...mapActions(useAccountV2Store, ['syncPushState']),
    },

    // The new-order chime lives in SellerOrderAlert (App.vue), so it rings on every seller page.
    async mounted() {
        this.syncPushState()
        await Promise.all([this.fetchOrders(), this.fetchSellerInfo()])
        this.startWatchingOrders()
    },

    beforeUnmount() {
        this.stopWatchingOrders()
    },
}
</script>

<template>
    <LayoutSellerHome>

        <template #Header>
            <SellerGreeting />
        </template>

        <template #Stats>
            <!-- Push off: orders only ring while the app is open, so nudge towards the switch on Me -->
            <router-link v-if="!notifications.orderUpdates" to="/seller/me" class="push-reminder">
                <BellRing :size="16" /> {{ $t('seller_home.push_reminder') }}
            </router-link>
            <SellerStatsGrid />
        </template>

        <template #ActionOrders>
            <div class="section-header">
                <div class="section-title">
                    {{ $t('seller_home.section_needs_action') }}
                </div>
                <q-btn-dropdown
                    flat dense no-caps
                    class="filter-dropdown"
                    :label="activeFilterLabel"
                    dropdown-icon="expand_more"
                >
                    <q-list class="dropdown-list">
                        <q-item
                            v-for="opt in filterOptions"
                            :key="opt.key"
                            clickable v-close-popup
                            :active="activeFilter === opt.key"
                            active-class="dropdown-active"
                            @click="activeFilter = opt.key"
                        >
                            <q-item-section>{{ opt.label }}</q-item-section>
                            <q-item-section side>
                                <q-badge :label="opt.count" color="grey-8" text-color="white" />
                            </q-item-section>
                        </q-item>
                    </q-list>
                </q-btn-dropdown>
            </div>

            <div v-if="showSkeleton" class="skeleton-list">
                <div v-for="n in 2" :key="n" class="skeleton-card">
                    <div class="sk-row">
                        <div>
                            <q-skeleton type="text" width="130px" animation="pulse" style="margin-bottom:5px;" />
                            <q-skeleton type="text" width="55px" animation="pulse" />
                        </div>
                        <q-skeleton type="rect" width="62px" height="22px" style="border-radius:12px;" animation="pulse" />
                    </div>
                    <q-skeleton type="rect" height="1px" animation="pulse" style="margin:10px 0;opacity:.3;" />
                    <div v-for="i in 2" :key="i" class="sk-row" style="margin-bottom:6px;">
                        <q-skeleton type="text" width="150px" animation="pulse" />
                        <q-skeleton type="text" width="65px" animation="pulse" />
                    </div>
                    <q-skeleton type="rect" height="1px" animation="pulse" style="margin:10px 0;opacity:.3;" />
                    <div class="sk-row" style="margin-bottom:14px;">
                        <q-skeleton type="text" width="35px" animation="pulse" />
                        <q-skeleton type="text" width="80px" animation="pulse" />
                    </div>
                    <div style="display:flex;gap:8px;justify-content:flex-end;">
                        <q-skeleton type="rect" width="80px" height="34px" style="border-radius:10px;" animation="pulse" />
                        <q-skeleton type="rect" width="120px" height="34px" style="border-radius:10px;" animation="pulse" />
                    </div>
                </div>
            </div>
            <ActionOrdersList v-else :orders="filteredActionOrders" />
        </template>

    </LayoutSellerHome>
</template>

<style lang="scss" scoped>
.push-reminder {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    padding: 10px 12px;
    border-radius: 12px;
    background: rgba(245, 166, 35, 0.12);
    border: 1px solid rgba(245, 166, 35, 0.35);
    color: var(--color-accent);
    font-size: 13px;
    font-weight: 600;
    text-decoration: none;
}

.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    padding-top: 4px;
}

.section-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
    font-family: $sariko-font-family-secondary;
}

.count-badge {
    font-size: 12px;
    font-weight: 700;
    background: var(--color-accent);
    color: #121b2f;
    border-radius: 10px;
    padding: 1px 7px;
    line-height: 1.6;
}

.filter-dropdown {
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 600;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 2px 8px;
}

.dropdown-list {
    background: #1f2940;
    min-width: 160px;
}

.dropdown-active {
    color: var(--color-accent);
}

.skeleton-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.skeleton-card {
    background: rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    padding: 16px;
}

.sk-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
</style>
