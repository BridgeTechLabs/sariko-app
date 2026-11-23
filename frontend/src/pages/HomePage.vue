<script>
import LayoutBaseHomePage from '@/layouts/home-page/LayoutBaseHomePage.vue'
import Header from '@/components/home-page/Header.vue'
import SearchBar from '@/components/home-page/SearchBar.vue'
import Categories from '@/components/home-page/Categories.vue'
import FoundingSellers from '@/components/home-page/FoundingSellers.vue';
import FeaturedDishes from '@/components/home-page/FeaturedDishes.vue';
import PromoCarousel from '@/components/home-page/PromoCarousel.vue'
import ZenPromoFloating from '@/components/home-page/ZenPromoFloating.vue'
import ZenFooterBanner from '@/components/home-page/ZenFooterBanner.vue'
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
        ZenFooterBanner,
        HomeFooter,
        BuyerMissingBanner
    },
    computed: {
        // unset = 'banner' (the default before the admin banners)
        showZenBanner() {
            return (import.meta.env.VITE_ZEN_AD_VARIANT || 'banner') === 'banner'
        },
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
            <ZenFooterBanner v-if="showZenBanner" />
            <HomeFooter />
        </template>

    </LayoutBaseHomePage>

    <ZenPromoFloating v-if="showZenFloating" />

</template>

<style scoped>
</style>