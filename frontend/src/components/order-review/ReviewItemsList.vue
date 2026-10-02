<script>
import ReviewItemCard from '@/components/order-review/ReviewItemCard.vue';
import { useOrderStore } from '@/stores/order/orderStore.js';

export default {
    components: { ReviewItemCard },

    computed: {
        order() {
            return useOrderStore().currentOrder
        },
        items() {
            // A dish deleted from the menu after the order leaves food_item_id null;
            // it cannot be reviewed (no row to attach to), so it is not listed.
            // Reviews are per dish, so two levels of one dish (S + L) show one card.
            const seen = new Set()
            return (this.order?.order_items || []).filter(item =>
                item.food_item_id && !seen.has(item.food_item_id) && seen.add(item.food_item_id))
        }
    }
}
</script>

<template>
    <div class="items">
        <template v-if="order">
            <div class="items-title">{{ $t('order_review.items_title') }}</div>

            <ReviewItemCard
                v-for="item in items"
                :key="item.id"
                :item="item"
            />
        </template>

        <template v-else>
            <q-skeleton type="text" width="45%" height="20px" animation="pulse" />
            <q-skeleton height="150px" animation="pulse" style="border-radius: 16px" />
            <q-skeleton height="150px" animation="pulse" style="border-radius: 16px" />
        </template>
    </div>
</template>

<style scoped>
.items {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.items-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
</style>
