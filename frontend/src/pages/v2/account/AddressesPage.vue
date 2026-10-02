<script>
import LayoutBaseAddresses from '@/layouts/v2/account/LayoutBaseAddresses.vue';
import AddressesTopBar from '@/components/v2/account/saved-addresses/AddressesTopBar.vue';
import SavedAddressList from '@/components/v2/account/saved-addresses/SavedAddressList.vue';
import DeliveryFeeTip from '@/components/v2/account/saved-addresses/DeliveryFeeTip.vue';

export default {
    name: 'AddressesPageV2',
    components: {
        LayoutBaseAddresses,
        AddressesTopBar,
        SavedAddressList,
        DeliveryFeeTip,
    }
}
</script>

<template>
    <LayoutBaseAddresses>

        <template #AddressesTopBar>
            <AddressesTopBar />
        </template>

        <template #SavedAddressList>
            <SavedAddressList />
        </template>

        <template #DeliveryFeeTip>
            <DeliveryFeeTip />
        </template>

    </LayoutBaseAddresses>
</template>
