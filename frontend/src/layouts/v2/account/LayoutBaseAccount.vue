<template>
    <div class="account-page">

        <slot name="ProfileHeader" />

        <div class="content-section">
            <slot name="OrderingMenu" />
            <slot name="PreferencesMenu" />
            <slot name="BecomeSellerCard" />
            <slot name="SupportMenu" />

            <p class="footer-note">{{ $t('account_v2.footer') }}</p>
        </div>

    </div>
</template>

<style scoped>
.account-page {
    min-height: 100vh;
    min-height: 100dvh;
    background: var(--background);
    font-family: var(--font-family-sans);
    /* Leave room for the fixed BottomNavigation */
    padding-bottom: calc(80px + env(safe-area-inset-bottom, 0px));
}

.content-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-24);
    padding: var(--space-24) var(--space-24) var(--space-16);
}

.footer-note {
    margin: 0;
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-placeholder);
    text-align: center;
}
</style>
