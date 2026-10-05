<script>
import { mapState, mapActions } from 'pinia';
import { useAccountV2Store } from '@/stores/v2/account/accountStore';
import { useThemeStore } from '@/stores/theme/themeStore';
import AccountMenuGroup from '@/components/v2/account/AccountMenuGroup.vue';
import AccountMenuRow from '@/components/v2/account/AccountMenuRow.vue';
import BaseSwitch from '@/components/v2/shared/BaseSwitch.vue';

export default {
    components: { AccountMenuGroup, AccountMenuRow, BaseSwitch },

    computed: {
        ...mapState(useAccountV2Store, ['notifications']),
        ...mapState(useThemeStore, ['theme']),

        languageLabel() {
            return this.$i18n.locale === 'vi' ? 'Tiếng Việt' : 'English'
        },
    },

    methods: {
        ...mapActions(useAccountV2Store, ['toggleNotification']),
        ...mapActions(useThemeStore, ['toggleTheme']),
    },
}
</script>

<template>
    <AccountMenuGroup :title="$t('account_v2.section_preferences')">
        <AccountMenuRow
            icon="globe"
            :label="$t('account_v2.language')"
            :value="languageLabel"
            @click="$router.push({ name: 'account-language-v2' })"
        />
        <AccountMenuRow
            icon="lock"
            :label="$t('account_v2.change_password')"
            @click="$router.push({ name: 'account-change-password-v2' })"
        />
        <AccountMenuRow
            icon="moon"
            :label="$t('account_v2.appearance')"
            :value="$t(`account_v2.theme_${theme}`)"
            @click="toggleTheme"
        />
        <AccountMenuRow
            icon="bell"
            :label="$t('account_v2.order_updates')"
            @click="toggleNotification('orderUpdates')"
        >
            <template #trailing>
                <!-- No v-model: the click bubbles up to the row, which toggles -->
                <BaseSwitch :model-value="notifications.orderUpdates" :label="$t('account_v2.order_updates')" />
            </template>
        </AccountMenuRow>
        <AccountMenuRow
            icon="bell"
            :label="$t('account_v2.seller_news')"
            @click="toggleNotification('sellerNews')"
        >
            <template #trailing>
                <!-- No v-model: the click bubbles up to the row, which toggles -->
                <BaseSwitch :model-value="notifications.sellerNews" :label="$t('account_v2.seller_news')" />
            </template>
        </AccountMenuRow>
    </AccountMenuGroup>
</template>

