<script>
import LayoutBaseSettings from '@/layouts/account/LayoutBaseSettings.vue';
import AddressForm from '@/components/account/AddressForm.vue';

// One buyer delivery address: /account/address/:id, or /account/address/new to add one.
export default {
    name: 'DeliveryAddressDetailPage',
    components: { LayoutBaseSettings, AddressForm },
    computed: {
        id() {
            return this.$route.params.id
        },
    },
}
</script>

<template>
    <LayoutBaseSettings :title="$t(id === 'new' ? 'breadcrumbs.address_new_page' : 'breadcrumbs.address_detail_page')" :back-to="$route.query.from === 'cart' ? '/cart' : '/account/address'">
        <template #Content>
            <AddressForm :key="id" :address-id="id" />
        </template>
    </LayoutBaseSettings>
</template>
