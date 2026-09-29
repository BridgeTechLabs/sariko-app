<script>
import { mapState, mapWritableState } from 'pinia';
import { useSellerStore } from '@/stores/seller/sellerStore';
import { useCartStore } from '@/stores/cart/cartStore';
import FoodCard from '@/components/seller/seller-page/FoodCard.vue'
import MenuEmptyState from '@/components/seller/seller-page/MenuEmptyState.vue'
import ModalCartConflict from '@/components/order-cart/ModalCartConflict.vue';
import { foodPriceDisplay, hasVariants } from '@/utils/priceDisplay';

export default {
    methods: { foodPriceDisplay, hasVariants },
    components: {
        FoodCard,
        MenuEmptyState,
        ModalCartConflict
    },

    computed: {
        ...mapState(useSellerStore, [
            "menu",
            "selectedCategoryMenu"
        ]),

        ...mapWritableState(useCartStore, [
            "isShowModalCartConflict"
        ])
    }
}
</script>

<template>

    <div class="background">

        <div class="container">
            <div v-if="menu.length > 0" class="food-list">
                <FoodCard
                v-for="food in menu"
                :key="food.id"
                :item-id="food.id"
                :name="food.name"
                :price="foodPriceDisplay(food)"
                :has-variants="hasVariants(food)"
                :imgSrc="food.image_url ? food.image_url : '/images/default-food-image.webp'"
                :unit-label="food.unit_label || 'pcs'"
                :preorder-day="food.preorder_day || 0"
                :rating-avg="food.rating_avg"
                :rating-count="food.rating_count || 0"
                />
            </div>
            <MenuEmptyState v-else />
        </div>

    </div>

    <q-dialog v-model="isShowModalCartConflict">
        <ModalCartConflict />
    </q-dialog>

</template>

<style lang="scss" scoped>
.background {
    padding: 0px 10px;
}

.food-list {
    display: flex;
    flex-direction: column;
}
</style>