<script>
import { mapState } from 'pinia';
import { useAuthStore } from '@/stores/auth/authStore';
import LayoutBaseSettings from '@/layouts/account/LayoutBaseSettings.vue';
import AddressForm from '@/components/account/AddressForm.vue';
import AddressList from '@/components/account/AddressList.vue';

export default {
    name: 'DeliveryAddressPage',
    components: { LayoutBaseSettings, AddressForm, AddressList },
    computed: {
        ...mapState(useAuthStore, ['user']),
        pageTitle() {
            return this.user?.isSeller
                ? this.$t('breadcrumbs.store_address_page')
                : this.$t('breadcrumbs.delivery_address_page')
        }
    }
}
</script>

<template>
    <LayoutBaseSettings :title="pageTitle" back-to="/account">
        <template #Content>
            <AddressForm v-if="user?.isSeller" />
            <AddressList v-else />
        </template>
    </LayoutBaseSettings>
</template>
