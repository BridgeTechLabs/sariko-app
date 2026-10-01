<script>
import { mapState, mapActions } from 'pinia';
import { useAccountV2Store } from '@/stores/v2/account/accountStore';
import SavedAddressCard from '@/components/v2/account/saved-addresses/SavedAddressCard.vue';
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';

export default {
    components: { SavedAddressCard, BaseIcon },

    computed: {
        ...mapState(useAccountV2Store, ['addresses']),
    },

    mounted() {
        this.fetchAccount()
    },

    methods: {
        ...mapActions(useAccountV2Store, ['fetchAccount']),
    },
}
</script>

<template>
    <SavedAddressCard
        v-for="address in addresses"
        :key="address.id"
        :address="address"
    />

    <button class="add-new" type="button" @click="$router.push({ name: 'account-address-new-v2' })">
        <BaseIcon name="plus" :size="20" />
        <span>{{ $t('account_v2.address_add') }}</span>
    </button>
</template>

<style scoped>
.add-new {
    width: 100%;
    height: 56px;
    padding: 0 var(--space-16);
    border: 1.5px dashed var(--input);
    border-radius: var(--radius-xl);
    background: transparent;
    color: var(--icon-default);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-8);
    font-family: inherit;
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
    cursor: pointer;
}

.add-new span {
    color: var(--text-primary);
}
</style>
