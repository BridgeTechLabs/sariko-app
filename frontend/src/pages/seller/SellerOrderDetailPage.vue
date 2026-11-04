<script>
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import LayoutSellerOrderDetail from '@/layouts/seller/LayoutSellerOrderDetail.vue';
import SellerOrderDetailContent from '@/components/seller-order-detail/SellerOrderDetailContent.vue';
import SellerOrderActionBar from '@/components/seller-order-detail/SellerOrderActionBar.vue';
import PageBreadcrumbs from '@/components/shared/PageBreadcrumbs.vue';
import OrderComplaintSection from '@/components/complaints/OrderComplaintSection.vue';

export default {
    name: 'SellerOrderDetailPage',

    components: { LayoutSellerOrderDetail, SellerOrderDetailContent, SellerOrderActionBar, PageBreadcrumbs, OrderComplaintSection },

    props: ['orderId'],

    computed: {
        store()    { return useDashboardStore() },
        order()    { return this.store.orderDetails },
        delivery() { return this.store.orderDelivery },
        loading()  { return this.store.orderDetailLoading },
    },

    async mounted() {
        const store = useDashboardStore()
        await store.loadOrderDetail(this.orderId)
        store.startWatchingOrderDetail(this.orderId)
    },

    beforeUnmount() {
        const store = useDashboardStore()
        store.stopWatchingOrderDetail()
        store.clearOrderDetail()
    },
}
</script>

<template>
    <LayoutSellerOrderDetail>

        <template #Header>
            <div class="page-header">
                <PageBreadcrumbs :title="$t('seller_order_detail.page_title')" backTo="/seller/orders" />
            </div>
        </template>

        <template #Content>
            <div v-if="loading" class="skeleton-list">
                <!-- Status card -->
                <div class="sk-card">
                    <div class="sk-row" style="margin-bottom:8px;">
                        <q-skeleton type="text" width="55px" animation="pulse" />
                        <q-skeleton type="rect" width="80px" height="22px" style="border-radius:12px;" animation="pulse" />
                    </div>
                    <q-skeleton type="text" width="160px" animation="pulse" />
                </div>
                <!-- Customer card -->
                <div class="sk-card">
                    <q-skeleton type="text" width="70px" animation="pulse" style="margin-bottom:12px;" />
                    <div v-for="i in 3" :key="i" class="sk-info-row">
                        <q-skeleton type="text" width="60px" animation="pulse" />
                        <q-skeleton type="text" width="130px" animation="pulse" />
                    </div>
                </div>
                <!-- Items card -->
                <div class="sk-card">
                    <q-skeleton type="text" width="50px" animation="pulse" style="margin-bottom:12px;" />
                    <div v-for="i in 3" :key="i" class="sk-info-row" style="margin-bottom:8px;">
                        <q-skeleton type="text" width="140px" animation="pulse" />
                        <q-skeleton type="text" width="65px" animation="pulse" />
                    </div>
                    <q-skeleton type="rect" height="1px" animation="pulse" style="margin:12px 0;opacity:.3;" />
                    <div v-for="i in 2" :key="`p${i}`" class="sk-info-row">
                        <q-skeleton type="text" width="70px" animation="pulse" />
                        <q-skeleton type="text" width="75px" animation="pulse" />
                    </div>
                </div>
                <!-- Payment card -->
                <div class="sk-card">
                    <q-skeleton type="text" width="65px" animation="pulse" style="margin-bottom:12px;" />
                    <div v-for="i in 2" :key="i" class="sk-info-row">
                        <q-skeleton type="text" width="60px" animation="pulse" />
                        <q-skeleton type="text" width="90px" animation="pulse" />
                    </div>
                </div>
                <!-- Timeline card -->
                <div class="sk-card">
                    <q-skeleton type="text" width="80px" animation="pulse" style="margin-bottom:16px;" />
                    <div v-for="i in 4" :key="i" class="sk-timeline-step">
                        <div class="sk-timeline-left">
                            <q-skeleton type="circle" width="14px" height="14px" animation="pulse" />
                            <div v-if="i < 4" class="sk-timeline-line" />
                        </div>
                        <q-skeleton type="text" :width="`${90 + i * 15}px`" animation="pulse" style="margin-top:1px;" />
                    </div>
                </div>
            </div>
            <SellerOrderDetailContent v-else-if="order" :order="order" :delivery="delivery" />
            <OrderComplaintSection v-if="order && !loading" role="seller" />
        </template>

        <template #Actions>
            <SellerOrderActionBar
                v-if="order && !loading"
                :order="order"
                :delivery="delivery"
            />
        </template>

    </LayoutSellerOrderDetail>
</template>

<style lang="scss" scoped>
.page-header {
    padding: 16px;
}

.skeleton-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.sk-card {
    background: rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    padding: 16px;
}

.sk-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.sk-info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    &:last-child { margin-bottom: 0; }
}

.sk-timeline-step {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    margin-bottom: 4px;
}

.sk-timeline-left {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 16px;
    flex-shrink: 0;
}

.sk-timeline-line {
    width: 2px;
    height: 28px;
    background: rgba(255, 255, 255, 0.1);
    margin: 3px 0;
}
</style>
