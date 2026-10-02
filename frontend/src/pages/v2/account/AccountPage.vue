<script>
import LayoutBaseAccount from '@/layouts/v2/account/LayoutBaseAccount.vue';
import ProfileHeader from '@/components/v2/account/ProfileHeader.vue';
import OrderingMenu from '@/components/v2/account/OrderingMenu.vue';
import PreferencesMenu from '@/components/v2/account/PreferencesMenu.vue';
import BecomeSellerCard from '@/components/v2/account/BecomeSellerCard.vue';
import SupportMenu from '@/components/v2/account/SupportMenu.vue';

export default {
    name: 'AccountPageV2',
    components: {
        LayoutBaseAccount,
        ProfileHeader,
        OrderingMenu,
        PreferencesMenu,
        BecomeSellerCard,
        SupportMenu,
    }
}
</script>

<template>
    <LayoutBaseAccount>

        <template #ProfileHeader>
            <ProfileHeader />
        </template>

        <template #OrderingMenu>
            <OrderingMenu />
        </template>

        <template #PreferencesMenu>
            <PreferencesMenu />
        </template>

        <template #BecomeSellerCard>
            <BecomeSellerCard />
        </template>

        <template #SupportMenu>
            <SupportMenu />
        </template>

    </LayoutBaseAccount>
</template>
