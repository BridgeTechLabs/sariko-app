<script>

export default {
    mounted() {
        const heightHeaderContent = this.$refs.headerContent?.offsetHeight || 0
        // const heightSearchBarContent = this.$refs.searchBarContent?.offsetHeight || 0
        const heightCategoriesContent = this.$refs.categoriesContent?.offsetHeight || 0
        const heightBannerContent = this.$refs.bannerContent?.offsetHeight || 0
        const foundingSellerContent = this.$refs.foundingSellerContent?.offsetHeight || 0
    }
}

</script>

<template>
    <div class="background">
        <div class="container">

            <div ref="headerContent" class="header-section">
                <slot name="Header" />
            </div>

            <div class="zen-promo-section">
                <slot name="ZenPromo" />
            </div>

            <div ref="searchBarContent" class="search-bar-section">
                <slot name="SearchBar" />
            </div>

            <div ref="categoriesContent" class="categories-chips-section">
                <slot name="Categories" />
            </div>

            <q-separator class="seperator"/>

            <div ref="foundingSellerContent" class="founding-sellers-section">
                <slot name="FoundingSellers" />
            </div>

            <div class="featured-dishes-section">
                <slot name="FeaturedDishes" />
            </div>

            <div ref="bannerContent" class="banner">
                <slot name="Banner" />
            </div>

            <div class="footer-section">
                <slot name="Footer" />
            </div>

        </div>
    </div>
</template>

<style scoped>
.background {
    max-width: 1200px;
    height: 100vh;
    height: 100dvh;
}

.container {
    background: var(--bg-main);
    padding: 20px;
    padding-top: calc(16px + env(safe-area-inset-top, 0));
    padding-bottom: var(--bottom-nav-height);
}
.zen-promo-section {
    margin-bottom: 16px;
}

.search-bar-section {
    width: 100%;
    margin-bottom: 24px;
}

.categories-chips-section {
    margin-bottom: 20px;
}

.seperator {
    background-color: #373c45;
    margin-bottom: 10px;
}

.founding-sellers-section {
    margin-bottom: 32px;
}

.featured-dishes-section {
    margin-bottom: 32px;
}

.footer-section {
    margin-top: 24px;
}

</style>