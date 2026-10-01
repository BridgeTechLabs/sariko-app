<script>
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';

// Small status/tag label. Text goes in the default slot.
export default {
    components: { BaseIcon },

    props: {
        tone: {
            type: String,
            default: 'gold',
            validator: (value) => ['gold', 'saffron', 'success', 'warning', 'error', 'neutral'].includes(value),
        },
        icon: {
            type: String,
            default: null,
        },
    },
}
</script>

<template>
    <span class="base-pill" :class="tone">
        <BaseIcon v-if="icon" :name="icon" :size="12" />
        <slot />
    </span>
</template>

<style scoped>
.base-pill {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-8);
    height: 24px;
    padding: 0 var(--space-8);
    border-radius: var(--radius-full);
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
    white-space: nowrap;
}

.gold {
    background: var(--brand-gold-soft);
    color: var(--text-gold);
}

.saffron {
    background: var(--brand-saffron-soft);
    color: var(--text-saffron);
}

.success {
    background: var(--status-success-soft);
    color: var(--status-success-foreground);
}

.warning {
    background: var(--status-warning-soft);
    color: var(--status-warning-foreground);
}

.error {
    background: var(--status-error-soft);
    color: var(--status-error-foreground);
}

.neutral {
    background: var(--status-neutral-soft);
    color: var(--status-neutral-foreground);
}
</style>
