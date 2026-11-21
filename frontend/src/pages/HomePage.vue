<script>
import LayoutBaseHomePage from '@/layouts/home-page/LayoutBaseHomePage.vue'
import Header from '@/components/home-page/Header.vue'
import SearchBar from '@/components/home-page/SearchBar.vue'
import Categories from '@/components/home-page/Categories.vue'
import FoundingSellers from '@/components/home-page/FoundingSellers.vue';
import FeaturedDishes from '@/components/home-page/FeaturedDishes.vue';
import PromoCarousel from '@/components/home-page/PromoCarousel.vue'
import ZenPromoFloating from '@/components/home-page/ZenPromoFloating.vue'
import HomeFooter from '@/components/home-page/HomeFooter.vue'
import BuyerMissingBanner from '@/components/home-page/BuyerMissingBanner.vue'

export default {
    name: 'HomePage',
    components: {
        LayoutBaseHomePage,
        Header,
        Categories,
        SearchBar,
        FoundingSellers,
        FeaturedDishes,
        PromoCarousel,
        ZenPromoFloating,
        HomeFooter,
        BuyerMissingBanner
    },
    computed: {
        showZenFloating() {
            return import.meta.env.VITE_ZEN_AD_VARIANT === 'floating'
        }
    }
}
</script>


<template>

    <LayoutBaseHomePage>

        <template #Header>
            <Header />
            <BuyerMissingBanner />
        </template>

        <template #ZenPromo>
            <PromoCarousel />
        </template>

        <template #SearchBar>
            <SearchBar />
        </template>

        <template #Categories>
            <Categories />
        </template>

        <template #FoundingSellers>
            <FoundingSellers />
        </template>

        <template #FeaturedDishes>
            <FeaturedDishes />
        </template>

        <template #Footer>
            <HomeFooter />
        </template>

    </LayoutBaseHomePage>

    <ZenPromoFloating v-if="showZenFloating" />

</template>

<style scoped>
</style>