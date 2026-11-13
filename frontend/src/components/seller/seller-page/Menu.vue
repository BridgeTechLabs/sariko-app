<script>
import { mapState } from 'pinia';
import { useSellerStore } from '@/stores/seller/sellerStore';
import FoodCard from '@/components/seller/seller-page/FoodCard.vue'
import MenuEmptyState from '@/components/seller/seller-page/MenuEmptyState.vue'
import { foodPriceDisplay, picksOnDetail } from '@/utils/priceDisplay';
import { portionsLeftToday, preorderPortions } from '@/utils/portions';

export default {
    methods: { foodPriceDisplay, picksOnDetail, portionsLeftToday, preorderPortions },
    components: {
        FoodCard,
        MenuEmptyState,
    },

    computed: {
        ...mapState(useSellerStore, [
            "menu",
            "selectedCategoryMenu"
        ]),
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
                :has-variants="picksOnDetail(food)"
                :imgSrc="food.image_url ? food.image_url : '/images/default-food-image.webp'"
                :unit-label="food.unit_label || 'pcs'"
                :preorder-day="food.preorder_day || 0"
                :is-available="food.is_available !== false && !food.options_sold_out"
                :portions-left="portionsLeftToday(food)"
                :preorder-portions="preorderPortions(food)"
                :rating-avg="food.rating_avg"
                :rating-count="food.rating_count || 0"
                />
            </div>
            <MenuEmptyState v-else />
        </div>

    </div>

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