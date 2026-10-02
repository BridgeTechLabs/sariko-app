<script>
import { mapState } from 'pinia';
import { useAccountV2Store } from '@/stores/v2/account/accountStore';
import AccountMenuGroup from '@/components/v2/account/AccountMenuGroup.vue';
import AccountMenuRow from '@/components/v2/account/AccountMenuRow.vue';

export default {
    components: { AccountMenuGroup, AccountMenuRow },

    computed: {
        ...mapState(useAccountV2Store, ['savedAddressCount', 'defaultPayment', 'stats']),
    },
}
</script>

<template>
    <AccountMenuGroup :title="$t('account_v2.section_ordering')">
        <AccountMenuRow
            icon="map-pin"
            :label="$t('account_v2.saved_addresses')"
            :value="$t('account_v2.saved_count', { count: savedAddressCount })"
            @click="$router.push({ name: 'account-addresses-v2' })"
        />
        <AccountMenuRow
            icon="credit-card"
            :label="$t('account_v2.default_payment')"
            :value="defaultPayment"
        />
        <AccountMenuRow
            icon="heart"
            :label="$t('account_v2.sellers_following')"
            :value="stats.following"
        />
        <AccountMenuRow
            icon="star"
            icon-filled
            :label="$t('account_v2.my_reviews')"
            :value="stats.reviews"
        />
    </AccountMenuGroup>
</template>
