<script>
import LayoutBaseSettings from '@/layouts/account/LayoutBaseSettings.vue'
import SellerStoreProfile from '@/components/seller-me/SellerStoreProfile.vue'

// The seller's one profile page (Edit Profile on Me): store fields, then the legal groups.
export default {
    name: 'SellerStoreProfilePage',
    components: { LayoutBaseSettings, SellerStoreProfile },
}
</script>

<template>
    <LayoutBaseSettings :title="$t('seller_profile.store_page_title')" back-to="/seller/me">
        <template #Content>
            <SellerStoreProfile />
        </template>
    </LayoutBaseSettings>
</template>
