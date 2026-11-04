<template>
    <!-- One scroll area for the whole page: greeting + stats scroll away so the orders get the screen -->
    <div class="seller-home-page">
        <div class="header-section">
            <slot name="Header" />
        </div>
        <div class="stats-section">
            <slot name="Stats" />
        </div>
        <slot name="ActionOrders" />
    </div>
</template>

<style lang="scss" scoped>
.seller-home-page {
    height: 100vh;
    height: 100dvh;
    overflow-y: auto;
    background: var(--bg-main);
    font-family: $sariko-font-family-secondary;
    padding: 20px 16px;
    padding-top: calc(20px + env(safe-area-inset-top, 0));
    padding-bottom: calc(var(--bottom-nav-height, 72px) + 16px);
}

.header-section {
    margin-bottom: 20px;
}

.stats-section {
    margin-bottom: 20px;
}
</style>
