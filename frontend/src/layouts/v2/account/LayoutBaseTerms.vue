<template>
    <div class="terms-page">

        <slot name="TermsTopBar" />

        <div class="body-section">
            <slot name="TermsContent" />
        </div>

    </div>
</template>

<style scoped>
.terms-page {
    min-height: 100vh;
    min-height: 100dvh;
    background: var(--background);
    font-family: var(--font-family-sans);
    padding-bottom: env(safe-area-inset-bottom, 0px);
}

.body-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-24);
    padding: var(--space-8) var(--space-24) var(--space-24);
    word-break: break-word;
}
</style>
