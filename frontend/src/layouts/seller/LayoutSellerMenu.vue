<template>
    <div class="seller-menu-page">
        <div class="header-section">
            <slot name="Header" />
        </div>
        <div class="content-section">
            <slot name="Content" />
        </div>
    </div>
</template>

<style lang="scss" scoped>
.seller-menu-page {
    display: flex;
    flex-direction: column;
    /* one screen high: the header and the tabs stay, the content scrolls under them (Jack 13/11) */
    height: 100vh;
    height: 100dvh;
    background: var(--bg-main);
    font-family: $sariko-font-family-secondary;
}

.header-section {
    flex-shrink: 0;
    padding-top: calc(8px + env(safe-area-inset-top, 0));
}

.content-section {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 0 16px;
    padding-bottom: calc(var(--bottom-nav-height, 72px) + 24px);
}
</style>
