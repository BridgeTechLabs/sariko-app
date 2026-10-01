<script>
// On/off switch, use with v-model.
export default {
    emits: ['update:modelValue'],

    props: {
        modelValue: {
            type: Boolean,
            default: false,
        },
        label: {
            type: String,
            default: null,
        },
        size: {
            type: Number,
            default: 28,
            validator: (value) => [28, 26].includes(value),
        },
    },
}
</script>

<template>
    <button
        class="base-switch"
        :class="[`size-${size}`, { on: modelValue }]"
        type="button"
        role="switch"
        :aria-checked="modelValue"
        :aria-label="label"
        @click="$emit('update:modelValue', !modelValue)"
    >
        <span class="knob" />
    </button>
</template>

<style scoped>
.base-switch {
    flex-shrink: 0;
    padding: 2px;
    border: none;
    border-radius: var(--radius-full);
    background: var(--border);
    display: flex;
    align-items: center;
    cursor: pointer;
    transition: background 0.2s ease;
}

.size-28 {
    width: 48px;
    height: 28px;
}

.size-26 {
    width: 44px;
    height: 26px;
}

.base-switch.on {
    background: var(--status-success);
}

.knob {
    flex-shrink: 0;
    border-radius: var(--radius-full);
    background: var(--card);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.16);
    transition: transform 0.2s ease;
}

.size-28 .knob {
    width: 24px;
    height: 24px;
}

.size-26 .knob {
    width: 22px;
    height: 22px;
}

.size-28.on .knob {
    transform: translateX(20px);
}

.size-26.on .knob {
    transform: translateX(18px);
}
</style>
