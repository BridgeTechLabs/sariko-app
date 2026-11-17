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
        if (this.left) return   // A24a: the buyer left while it loaded; going on would empty the order they opened next
        orderStore.startWatchingOrderDetail(this.orderId)

        // Independent of the order fetch above, so it runs regardless of status —
        // an order can turn 'done' mid-visit via the 10s poll.
        useReviewStore().checkOrderReview(this.orderId)

        // B2b: a delivery_failed order loads its ended trip once (LOST = no rebook); the poller stops at an ended trip
        if (this.shouldWatchDelivery || this.order?.status === 'delivery_failed') {
            useDeliveryStore().startWatching(this.orderId)
        }
    },

    beforeUnmount() {
        this.left = true
        useOrderStore().stopWatchingOrderDetail()
        useDeliveryStore().stopWatching()
        useDeliveryStore().currentDelivery = null   // T180 A24: coming back never flashes this order's trip
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
