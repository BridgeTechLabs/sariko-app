<script>
import AccountMenuGroup from '@/components/v2/account/AccountMenuGroup.vue';
import AccountMenuRow from '@/components/v2/account/AccountMenuRow.vue';

export default {
    components: { AccountMenuGroup, AccountMenuRow },
}
</script>

<template>
    <AccountMenuGroup :title="$t('account_v2.section_support')">
        <AccountMenuRow icon="help-circle" :label="$t('account_v2.help')" />
        <AccountMenuRow icon="receipt" :label="$t('account_v2.terms')" />
        <AccountMenuRow icon="shield" :label="$t('account_v2.privacy')" />
        <AccountMenuRow icon="truck" :label="$t('account_v2.shipping_policy')" />
        <AccountMenuRow icon="credit-card" :label="$t('account_v2.payment_methods')" />
        <AccountMenuRow icon="info" :label="$t('account_v2.about')" />
        <AccountMenuRow icon="log-out" :label="$t('account_v2.logout')" danger :chevron="false" />
    </AccountMenuGroup>
</template>
