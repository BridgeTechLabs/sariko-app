<script>
import LayoutBaseAddressForm from '@/layouts/v2/account/LayoutBaseAddressForm.vue';
import AddressFormTopBar from '@/components/v2/account/address-form/AddressFormTopBar.vue';
import AddressForm from '@/components/v2/account/address-form/AddressForm.vue';
import AddressFormSaveBar from '@/components/v2/account/address-form/AddressFormSaveBar.vue';

export default {
    name: 'AddressFormPageV2',
    components: {
        LayoutBaseAddressForm,
        AddressFormTopBar,
        AddressForm,
        AddressFormSaveBar,
    }
}
</script>

<template>
    <LayoutBaseAddressForm>

        <template #AddressFormTopBar>
            <AddressFormTopBar />
        </template>

        <template #AddressForm>
            <AddressForm />
        </template>

        <template #AddressFormSaveBar>
            <AddressFormSaveBar />
        </template>

    </LayoutBaseAddressForm>
</template>
