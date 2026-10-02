<script>
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';

// Pill-shaped button. Label goes in the default slot, `icon` renders after it.
// Pass the native `disabled` attribute for the disabled style.
export default {
    components: { BaseIcon },

    props: {
        variant: {
            type: String,
            default: 'primary',
            validator: (value) => ['primary', 'secondary', 'gold'].includes(value),
        },
        size: {
            type: Number,
            default: 48,
            validator: (value) => [48, 40].includes(value),
        },
        icon: {
            type: String,
            default: null,
        },
    },
}
</script>

<template>
    <button class="base-button" :class="[variant, `size-${size}`]" type="button">
        <slot />
        <BaseIcon v-if="icon" :name="icon" :size="size === 48 ? 20 : 16" />
    </button>
</template>

<style scoped>
.base-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-8);
    border: none;
    border-radius: var(--radius-full);
    font-family: inherit;
    font-weight: var(--font-weight-semibold);
    white-space: nowrap;
    cursor: pointer;
}

.size-48 {
    height: 48px;
    padding: 0 var(--space-24);
    font-size: var(--font-size-base);
    line-height: var(--font-line-height-24);
}

.size-40 {
    height: 40px;
    padding: 0 var(--space-16);
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
}

.primary {
    background: var(--primary);
    color: var(--primary-foreground);
}

.secondary {
    background: var(--secondary);
    color: var(--text-primary);
}

.gold {
    background: var(--brand-gold);
    color: var(--brand-gold-foreground);
}

.base-button:disabled {
    background: var(--button-disabled);
    color: var(--button-disabled-foreground);
    cursor: default;
}
</style>
