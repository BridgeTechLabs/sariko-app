<template>
    <div class="language-page">

        <slot name="LanguageTopBar" />

        <div class="body-section">
            <slot name="LanguageOptionList" />
        </div>

    </div>
</template>

<style scoped>
.language-page {
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
}
</style>
