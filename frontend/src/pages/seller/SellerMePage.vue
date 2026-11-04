<script>
import LayoutSellerMe from '@/layouts/seller/LayoutSellerMe.vue';
import SellerMeHeader from '@/components/seller-me/SellerMeHeader.vue';
import SellerMeShareCard from '@/components/seller-me/SellerMeShareCard.vue';
import SellerMeSettings from '@/components/seller-me/SellerMeSettings.vue';
import SellerMeEarnings from '@/components/seller-me/SellerMeEarnings.vue';
import SellerMeReviews from '@/components/seller-me/SellerMeReviews.vue';
import SellerMeSignOut from '@/components/seller-me/SellerMeSignOut.vue';

export default {
    name: 'SellerMePage',

    components: {
        LayoutSellerMe,
        SellerMeHeader,
        SellerMeShareCard,
        SellerMeSettings,
        SellerMeEarnings,
        SellerMeReviews,
        SellerMeSignOut,
    },
}
</script>

<template>
    <LayoutSellerMe>

        <template #ProfileHeader>
            <SellerMeHeader />
        </template>

        <template #Promote>
            <SellerMeShareCard />
        </template>

        <template #Settings>
            <SellerMeSettings />
        </template>

        <template #Earnings>
            <SellerMeEarnings />
        </template>

        <template #Reviews>
            <SellerMeReviews :preview="3" />
        </template>

        <template #SignOut>
            <SellerMeSignOut />
        </template>

        <template #Version>
            <div class="app-version">{{ $t('seller_me.app_version') }}</div>
        </template>

    </LayoutSellerMe>
</template>

<style scoped>
.app-version {
    text-align: center;
    font-size: 11px;
    color: var(--text-muted);
    padding: 4px 0 8px;
}
</style>
