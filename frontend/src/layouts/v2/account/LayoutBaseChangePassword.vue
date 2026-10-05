<template>
    <div class="change-password-page">

        <slot name="ChangePasswordTopBar" />

        <div class="form-section">
            <slot name="ChangePasswordForm" />
        </div>

        <slot name="ChangePasswordSaveBar" />

    </div>
</template>

<style scoped>
.change-password-page {
    min-height: 100vh;
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    background: var(--background);
    font-family: var(--font-family-sans);
}

.form-section {
    flex: 1;
    padding: var(--space-8) var(--space-24) var(--space-24);
}
</style>
