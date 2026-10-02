<template>
    <div class="address-form-page">

        <slot name="AddressFormTopBar" />

        <div class="form-section">
            <slot name="AddressForm" />
        </div>

        <slot name="AddressFormSaveBar" />

    </div>
</template>

<style scoped>
.address-form-page {
    min-height: 100vh;
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    background: var(--background);
    font-family: var(--font-family-sans);
}

.form-section {
    flex: 1;
    padding: 0 var(--space-24) var(--space-16);
}
</style>
