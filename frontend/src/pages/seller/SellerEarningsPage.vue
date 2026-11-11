<script>
import LayoutBaseSettings from '@/layouts/account/LayoutBaseSettings.vue'
import SellerMeEarnings from '@/components/seller-me/SellerMeEarnings.vue'

// Every order of the last days (by month) and every payout; the "Me" page shows only the newest few.
export default {
    name: 'SellerEarningsPage',
    components: { LayoutBaseSettings, SellerMeEarnings },
}
</script>

<template>
    <LayoutBaseSettings :title="$t('seller_me.section_title_earnings')" back-to="/seller/me">
        <template #Content>
            <div class="earnings-page">
                <SellerMeEarnings />
            </div>
        </template>
    </LayoutBaseSettings>
</template>

<style scoped>
/* the seller bottom nav sits over this page's bottom */
.earnings-page {
    padding-bottom: var(--bottom-nav-height, 72px);
}
</style>
