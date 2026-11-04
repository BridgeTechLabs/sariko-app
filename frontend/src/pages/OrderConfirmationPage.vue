<script>
import LayoutBaseOrderDetail from '@/layouts/order/order-details/LayoutBaseOrderDetail.vue';
import OrderBreadcrumbs from '@/components/order-details/OrderBreadcrumbs.vue';
import OrderStatusHeader from '@/components/order-details/OrderStatusHeader.vue';
import OrderInfoCard from '@/components/order-details/OrderInfoCard.vue';
import OrderActions from '@/components/order-details/OrderActions.vue';
import OrderReviewSection from '@/components/order-details/OrderReviewSection.vue';
import OrderComplaintSection from '@/components/complaints/OrderComplaintSection.vue';
import DeliveryTracker from '@/components/order-details/DeliveryTracker.vue';
import { useOrderStore } from '@/stores/order/orderStore.js';
import { useDeliveryStore } from '@/stores/delivery/deliveryStore.js';
import { useReviewStore } from '@/stores/review/reviewStore.js';

export default {
    components: {
        LayoutBaseOrderDetail,
        OrderBreadcrumbs,
        OrderStatusHeader,
        OrderInfoCard,
        OrderActions,
        OrderReviewSection,
        OrderComplaintSection,
        DeliveryTracker,
    },

    props: {
        orderId: {
            required: true,
            type: String
        }
    },

    computed: {
        order() {
            return useOrderStore().currentOrder
        },
        shouldShowTracker() {
            if (!this.order) return false
            return this.order.delivery_method === 'delivery'
                && ['confirmed', 'ready', 'done'].includes(this.order.status)
        },
        shouldWatchDelivery() {
            if (!this.order) return false
            return this.order.delivery_method === 'delivery'
                && ['ready', 'done'].includes(this.order.status)
        },
    },

    watch: {
        shouldWatchDelivery(val) {
            if (val) {
                useDeliveryStore().startWatching(this.orderId)
            } else {
                useDeliveryStore().stopWatching()
            }
        }
    },

    async mounted() {
        const orderStore = useOrderStore()
        await orderStore.getOrderDetail(this.orderId)
        orderStore.startWatchingOrderDetail(this.orderId)

        // Independent of the order fetch above, so it runs regardless of status —
        // an order can turn 'done' mid-visit via the 10s poll.
        useReviewStore().checkOrderReview(this.orderId)

        if (this.shouldWatchDelivery) {
            useDeliveryStore().startWatching(this.orderId)
        }
    },

    beforeUnmount() {
        useOrderStore().stopWatchingOrderDetail()
        useDeliveryStore().stopWatching()
    }
}
</script>

<template>
    <LayoutBaseOrderDetail>

        <template #Breadcrumbs>
            <OrderBreadcrumbs />
        </template>

        <template #StatusHeader>
            <OrderStatusHeader />
        </template>

        <template #DeliveryTracking>
            <DeliveryTracker v-if="shouldShowTracker" :order-status="order?.status" />
        </template>

        <template #OrderInfo>
            <OrderInfoCard />
        </template>

        <template #Review>
            <OrderReviewSection />
        </template>

        <template #Complaint>
            <OrderComplaintSection role="buyer" />
        </template>

        <template #Actions>
            <OrderActions />
        </template>

    </LayoutBaseOrderDetail>
</template>
