<script>
// Selectable chip (filters, single-choice options). Text goes in the default slot.
export default {
    props: {
        selected: {
            type: Boolean,
            default: false,
        },
    },
}
</script>

<template>
    <button
        class="base-chip"
        :class="{ selected }"
        type="button"
        :aria-pressed="selected"
    >
        <slot />
    </button>
</template>

<style scoped>
.base-chip {
    flex-shrink: 0;
    height: 40px;
    padding: 0 var(--space-16);
    border: none;
    border-radius: var(--radius-full);
    background: var(--chip-background);
    color: var(--chip-foreground);
    font-family: inherit;
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
    white-space: nowrap;
    cursor: pointer;
}

.base-chip.selected {
    background: var(--chip-background-selected);
    color: var(--chip-foreground-selected);
}
</style>
