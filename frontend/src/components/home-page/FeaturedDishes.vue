<script>
import { mapState, mapActions } from 'pinia';
import { useHomeStore } from '@/stores/homeStore';
import FeaturedDishCard from '@/components/home-page/FeaturedDishCard.vue';

export default {
    components: {
        FeaturedDishCard
    },

    data() {
        return {
            maxVisible: 6
        }
    },

    computed: {
        ...mapState(useHomeStore, ['featuredDishes']),

        visibleDishes() {
            return this.featuredDishes.slice(0, this.maxVisible)
        },

        hasMore() {
            return this.featuredDishes.length > this.maxVisible
        }
    },

    methods: {
        ...mapActions(useHomeStore, ['fetchFeaturedDishes'])
    },

    created() {
        this.fetchFeaturedDishes()
    }
}

</script>

<template>

<div class="container">

    <div class="group-title">

        <div class="title">
            🔥 {{ $t("home_page.section_featured_dishes.title") }}
        </div>
        <div class="button-see-all">
            <q-btn
            no-caps
            style="color: #bb8221; font-size: 12px; font-weight: 700;"
            :label="$t('home_page.section_featured_dishes.button_label_view_store')" 
            />
        </div>

    </div>
    <div>
        <!-- Skeleton -->
        <div v-if="featuredDishes.length === 0" class="row q-gutter-md" style="justify-content: stretch;">
            <div v-for="i in 4" :key="i" class="col-6" style="width: 45%;">
                <q-skeleton type="rect" height="140px" animation="pulse" style="border-radius: 0.75rem;" />
            </div>
        </div>

        <div v-else class="row q-gutter-md" style="justify-content: stretch;">
            <div v-for="(dish, index) in visibleDishes" :key="index" class="col-6" style="width: 45%;">
                <FeaturedDishCard
                :itemId="dish.id"
                :name="dish.name"
                :price="dish.price"
                :hasVariants="dish.hasVariants"
                :imgSrc="dish.imgSrc"
                :sellerSlug="dish.sellerSlug"
                :sellerId="dish.sellerId"
                :sellerName="dish.sellerName"
                />
            </div>
        </div>
        <div v-if="hasMore" class="see-all-container">
            <q-btn class="btn-see-all" flat dense no-caps>
                See all ({{ featuredDishes.length }})
            </q-btn>
        </div>
    </div>

</div>

</template>

<style lang="scss" scoped>
.container {
    font-family: $sariko-font-family-secondary;
}

.group-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 5px;
}

.title {
    font-size: 13px;
    font-weight: 700;
}

.see-all-container {
    display: flex;
    justify-content: center;
    margin-top: 16px;
}

.btn-see-all {
    color: $accent;
    font-size: 13px;
    font-weight: 600;
}
</style>