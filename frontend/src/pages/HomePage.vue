<script>
import LayoutBaseHomePage from '@/layouts/home-page/LayoutBaseHomePage.vue'
import Header from '@/components/home-page/Header.vue'
import SearchBar from '@/components/home-page/SearchBar.vue'
import Categories from '@/components/home-page/Categories.vue'
import FoundingSellers from '@/components/home-page/FoundingSellers.vue';
import FeaturedDishes from '@/components/home-page/FeaturedDishes.vue';
import Banner from '@/components/home-page/Banner.vue'
import ZenPromoBanner from '@/components/home-page/ZenPromoBanner.vue'
import ZenPromoFloating from '@/components/home-page/ZenPromoFloating.vue'
import HomeFooter from '@/components/home-page/HomeFooter.vue'

const ZEN_AD_VARIANT = import.meta.env.VITE_ZEN_AD_VARIANT || 'banner'

export default {
    name: 'HomePage',
    components: {
        LayoutBaseHomePage,
        Header,
        Categories,
        SearchBar,
        FoundingSellers,
        FeaturedDishes,
        Banner,
        ZenPromoBanner,
        ZenPromoFloating,
        HomeFooter
    },
    computed: {
        showZenBanner() {
            return ZEN_AD_VARIANT === 'banner'
        },
        showZenFloating() {
            return ZEN_AD_VARIANT === 'floating'
        }
    }
}
</script>


<template>

    <LayoutBaseHomePage>

        <template #Header>
            <Header />
        </template>

        <template v-if="showZenBanner" #ZenPromo>
            <ZenPromoBanner />
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

        <template #Banner>
            <Banner />
        </template>

        <template #Footer>
            <HomeFooter />
        </template>

    </LayoutBaseHomePage>

    <ZenPromoFloating v-if="showZenFloating" />

</template>

<style scoped>
</style>