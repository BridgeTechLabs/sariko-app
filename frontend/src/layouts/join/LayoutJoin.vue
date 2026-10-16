<script>
</script>

<template>
    <div class="join-background">
        <div class="join-container">
            <div class="section-join-header">
                <slot name="header" />
            </div>
            <div class="section-join-tip">
                <slot name="tip" />
            </div>
            <div class="section-join-content">
                <slot name="content" />
            </div>
        </div>
    </div>
</template>

<style lang="scss" scoped>
.join-background {
    min-height: 100vh;
    min-height: 100dvh;
    background-color: #121b2f;
    color: #fff;
    font-family: $sariko-font-family-secondary;
    padding: 32px 0 80px;
}

.join-container {
    width: 100%;
    padding: 0 16px;
}

.section-join-header {
    margin-bottom: 20px;
}

.section-join-tip:not(:empty) {
    margin-bottom: 16px;
}
</style>

<!-- Shared by the /join step components (layout owns the CSS). -->
<style lang="scss">
.join-step {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 4px 0 8px;
}

.join-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 4px 14px;
}

.join-section-title {
    font-family: $sariko-font-family-primary;
    font-size: 17px;
    font-weight: 600;
    color: #fff;
    margin-top: 6px;
}

.join-label {
    font-size: 13px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.75);
    margin-bottom: 4px;
}

.join-hint {
    font-size: 12px;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.55);
}

.join-error {
    font-size: 12px;
    color: #ef4444;
}

.join-card {
    background: #1f2940;
    border-radius: 16px;
    padding: 14px;
}

.join-link {
    color: #f5a623;
    font-weight: 600;
    text-decoration: none;
}
</style>
