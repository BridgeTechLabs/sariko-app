<template>
    <div class="addresses-page">

        <slot name="AddressesTopBar" />

        <div class="list-section">
            <slot name="SavedAddressList" />
            <slot name="DeliveryFeeTip" />
        </div>

    </div>
</template>

<style scoped>
.addresses-page {
    min-height: 100vh;
    min-height: 100dvh;
    background: var(--background);
    font-family: var(--font-family-sans);
    padding-bottom: env(safe-area-inset-bottom, 0px);
}

.list-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-16);
    padding: 0 var(--space-24) var(--space-16);
}
</style>
