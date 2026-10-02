<script>
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';

// One row of an AccountMenuGroup. Use the #trailing slot to replace value + chevron (e.g. a toggle).
export default {
    components: { BaseIcon },

    props: {
        // BaseIcon name
        icon: {
            type: String,
            required: true,
        },
        label: {
            type: String,
            required: true,
        },
        value: {
            type: [String, Number],
            default: null,
        },
        iconFilled: {
            type: Boolean,
            default: false,
        },
        danger: {
            type: Boolean,
            default: false,
        },
        chevron: {
            type: Boolean,
            default: true,
        },
    },
}
</script>

<template>
    <div class="row" :class="{ danger }">
        <div class="icon-box">
            <BaseIcon :name="icon" :size="18" :filled="iconFilled" />
        </div>
        <span class="label">{{ label }}</span>
        <slot name="trailing">
            <span v-if="value !== null" class="value">{{ value }}</span>
            <BaseIcon v-if="chevron" class="chevron" name="chevron-right" :size="18" />
        </slot>
    </div>
</template>

<style scoped>
.row {
    display: flex;
    align-items: center;
    gap: var(--space-16);
    height: 56px;
    padding: 0 var(--space-16);
    cursor: pointer;
}

.row + .row {
    border-top: var(--border-default) solid var(--divider);
}

.icon-box {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    border-radius: var(--radius-lg);
    background: var(--secondary);
    color: var(--icon-default);
    display: flex;
    align-items: center;
    justify-content: center;
}

.label {
    flex: 1;
    min-width: 0;
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.value {
    flex-shrink: 0;
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-secondary);
    white-space: nowrap;
}

.chevron {
    flex-shrink: 0;
    color: var(--icon-muted);
}

.danger .icon-box {
    background: var(--status-error-soft);
    color: var(--destructive);
}

.danger .label {
    color: var(--destructive);
}
</style>
