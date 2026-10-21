<template>
    <div class="order-detail-page">

        <div class="breadcrumbs-section">
            <slot name="Breadcrumbs" />
        </div>

        <div class="status-header-section">
            <slot name="StatusHeader" />
        </div>

        <div class="delivery-tracking-section">
            <slot name="DeliveryTracking" />
        </div>

        <div class="order-info-section">
            <slot name="OrderInfo" />
        </div>

        <div class="review-section">
            <slot name="Review" />
        </div>

        <div class="complaint-section">
            <slot name="Complaint" />
        </div>

        <div class="actions-section">
            <slot name="Actions" />
        </div>

    </div>
</template>

<style lang="scss" scoped>
.order-detail-page {
    min-height: 100vh;
    min-height: 100dvh;
    font-family: $sariko-font-family-secondary;
}

.breadcrumbs-section {
    padding: 15px;
}

.status-header-section {
    padding: 24px 16px 0 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.delivery-tracking-section {
    padding: 0 16px;
}

.order-info-section {
    padding: 28px 16px;
}

/* Renders only on done+paid orders. No vertical padding, so it collapses to zero
   height otherwise; the bottom gap comes from actions-section's padding either way. */
.review-section {
    padding: 0 16px;
}

/* Same collapse rule: empty unless the order has complaints or can get one */
.complaint-section {
    padding: 16px 16px 0;
}

.complaint-section:empty {
    padding: 0;
}

.actions-section {
    padding: 0 16px 24px 16px;
}
</style>
