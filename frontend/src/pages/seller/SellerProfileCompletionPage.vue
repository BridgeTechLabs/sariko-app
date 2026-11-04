<script>
import LayoutBaseSettings from '@/layouts/account/LayoutBaseSettings.vue'
import ProfileCompletionForm from '@/components/seller-profile/ProfileCompletionForm.vue'

export default {
    name: 'SellerProfileCompletionPage',
    components: { LayoutBaseSettings, ProfileCompletionForm },
}
</script>

<template>
    <LayoutBaseSettings :title="$t('seller_profile.page_title')" back-to="/seller/me">
        <template #Content>
            <ProfileCompletionForm />
        </template>
    </LayoutBaseSettings>
</template>
