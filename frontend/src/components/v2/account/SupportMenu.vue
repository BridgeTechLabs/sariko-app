<script>
import { mapActions } from 'pinia';
import { useAuthStore } from '@/stores/auth/authStore';
import AccountMenuGroup from '@/components/v2/account/AccountMenuGroup.vue';
import AccountMenuRow from '@/components/v2/account/AccountMenuRow.vue';

export default {
    components: { AccountMenuGroup, AccountMenuRow },

    data() {
        return {
            signingOut: false,
        }
    },

    methods: {
        ...mapActions(useAuthStore, ['onClickedSignout']),

        async signOut() {
            if (this.signingOut) return
            this.signingOut = true
            try {
                await this.onClickedSignout()
            } finally {
                this.signingOut = false
            }
        },
    },
}
</script>

<template>
    <AccountMenuGroup :title="$t('account_v2.section_support')">
        <AccountMenuRow icon="help-circle" :label="$t('account_v2.help')" />
        <AccountMenuRow
            icon="receipt"
            :label="$t('account_v2.terms')"
            @click="$router.push({ name: 'account-terms-v2' })"
        />
        <AccountMenuRow icon="shield" :label="$t('account_v2.privacy')" />
        <AccountMenuRow icon="truck" :label="$t('account_v2.shipping_policy')" />
        <AccountMenuRow icon="credit-card" :label="$t('account_v2.payment_methods')" />
        <AccountMenuRow icon="info" :label="$t('account_v2.about')" />
        <AccountMenuRow
            icon="log-out"
            :label="$t('account_v2.logout')"
            danger
            :chevron="false"
            @click="signOut"
        />
    </AccountMenuGroup>
</template>
