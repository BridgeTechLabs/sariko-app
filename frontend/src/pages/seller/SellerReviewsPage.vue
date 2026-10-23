<script>
import LayoutBaseSettings from '@/layouts/account/LayoutBaseSettings.vue'
import SellerMeReviews from '@/components/seller-me/SellerMeReviews.vue'

// Every review of the seller, 10 at a time ("See more"); the "Me" page shows only the newest 3.
export default {
    name: 'SellerReviewsPage',
    components: { LayoutBaseSettings, SellerMeReviews },
}
</script>

<template>
    <LayoutBaseSettings :title="$t('seller_me.section_title_reviews')" back-to="/seller/me">
        <template #Content>
            <div class="reviews-page">
                <SellerMeReviews />
            </div>
        </template>
    </LayoutBaseSettings>
</template>

<style scoped>
/* the seller bottom nav sits over this page's bottom: keep "See more" above it */
.reviews-page {
    padding-bottom: var(--bottom-nav-height, 72px);
}
</style>
