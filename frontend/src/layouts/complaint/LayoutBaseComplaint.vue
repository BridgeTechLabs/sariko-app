<template>
    <div class="complaint-page">

        <div class="breadcrumbs-section">
            <slot name="Breadcrumbs" />
        </div>

        <div class="content-section">
            <slot name="Content" />
        </div>

    </div>
</template>

<style lang="scss" scoped>
.complaint-page {
    min-height: 100vh;
    min-height: 100dvh;
    font-family: $sariko-font-family-secondary;
}

.breadcrumbs-section {
    padding: 15px;
}

/* Bottom padding clears the bottom navigation */
.content-section {
    padding: 4px 16px 110px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}
</style>
