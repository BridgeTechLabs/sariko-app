<script>
// Placeholder copy until legal text is approved — no API yet.
const SECTIONS = ['using', 'orders', 'delivery', 'refunds'];

export default {
    data() {
        return {
            sections: SECTIONS,
        }
    },
}
</script>

<template>
    <p class="caption">{{ $t('account_v2.terms_last_updated') }}</p>

    <section v-for="section in sections" :key="section" class="section">
        <h2 class="heading">{{ $t(`account_v2.terms_${section}_title`) }}</h2>
        <p class="body">{{ $t(`account_v2.terms_${section}_body`) }}</p>
    </section>

    <p class="caption note">{{ $t('account_v2.terms_placeholder_note') }}</p>
</template>

<style scoped>
p,
h2 {
    margin: 0;
}

.caption {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-regular);
    color: var(--muted-foreground);
}

.note {
    color: var(--status-warning);
}

.section {
    display: flex;
    flex-direction: column;
    gap: var(--space-8);
    font-size: var(--font-size-base);
    line-height: var(--font-line-height-24);
}

.heading {
    font-size: inherit;
    line-height: inherit;
    font-weight: var(--font-weight-semibold);
    color: var(--foreground);
}

.body {
    font-weight: var(--font-weight-regular);
    color: var(--muted-foreground);
}
</style>
