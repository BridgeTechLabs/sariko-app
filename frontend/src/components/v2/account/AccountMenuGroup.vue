<script>
// Section title + card; rows go in the default slot
export default {
    props: {
        title: {
            type: String,
            required: true,
        },
    },
}
</script>

<template>
    <section class="menu-group">
        <p class="title">{{ title }}</p>
        <div class="card">
            <slot />
        </div>
    </section>
</template>

<style scoped>
.menu-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-8);
}

.title {
    margin: 0;
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
    color: var(--text-secondary);
    text-transform: uppercase;
}

.card {
    background: var(--card);
    border-radius: var(--radius-xl);
    box-shadow: 0 2px 8px color-mix(in srgb, var(--brand-navy) 5%, transparent);
    overflow: hidden;
}
</style>
