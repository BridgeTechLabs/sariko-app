<script>
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';

// Labeled text input, use with v-model. Extra attrs (type, inputmode, autocomplete, @blur...)
// go to the <input>/<textarea>. A non-empty `error` switches to the error state and replaces `hint`.
export default {
    components: { BaseIcon },

    inheritAttrs: false,

    emits: ['update:modelValue'],

    props: {
        modelValue: {
            type: String,
            default: '',
        },
        label: {
            type: String,
            required: true,
        },
        placeholder: {
            type: String,
            default: '',
        },
        required: {
            type: Boolean,
            default: false,
        },
        // Muted text after the label, e.g. "(optional)"
        labelNote: {
            type: String,
            default: null,
        },
        icon: {
            type: String,
            default: null,
        },
        // Fixed text before the input, e.g. phone country code "+84"
        prefix: {
            type: String,
            default: null,
        },
        hint: {
            type: String,
            default: null,
        },
        error: {
            type: String,
            default: null,
        },
        multiline: {
            type: Boolean,
            default: false,
        },
    },
}
</script>

<template>
    <label class="base-text-field">
        <span class="label">
            {{ label }}
            <span v-if="required" class="required">*</span>
            <span v-if="labelNote" class="note">{{ labelNote }}</span>
        </span>

        <span class="input" :class="{ error: !!error, multiline }">
            <BaseIcon v-if="icon" class="input-icon" :name="icon" :size="20" />
            <span v-if="prefix" class="prefix">{{ prefix }}</span>
            <textarea
                v-if="multiline"
                v-bind="$attrs"
                :value="modelValue"
                :placeholder="placeholder"
                @input="$emit('update:modelValue', $event.target.value)"
            />
            <input
                v-else
                v-bind="$attrs"
                :value="modelValue"
                :placeholder="placeholder"
                @input="$emit('update:modelValue', $event.target.value)"
            />
        </span>

        <span v-if="error" class="helper error-text">{{ error }}</span>
        <span v-else-if="hint" class="helper">{{ hint }}</span>
    </label>
</template>

<style scoped>
.base-text-field {
    display: flex;
    flex-direction: column;
    gap: var(--space-8);
}

.label {
    display: flex;
    gap: var(--space-8);
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.required {
    color: var(--status-error);
}

.note {
    font-weight: var(--font-weight-regular);
    color: var(--text-secondary);
}

.input {
    height: 52px;
    display: flex;
    align-items: center;
    gap: var(--space-16);
    padding: 0 var(--space-16);
    background: var(--card);
    border: var(--border-default) solid var(--input);
    border-radius: var(--radius-lg);
}

.input.error {
    border-color: var(--destructive);
}

/* Figma focus: 2px border — shrink padding by 1px so content doesn't shift */
.input:focus-within {
    border-width: var(--border-strong);
    border-color: var(--ring);
    padding: 0 calc(var(--space-16) - 1px);
}

.input.multiline {
    height: 80px;
    align-items: stretch;
    padding-top: var(--space-16);
}

.input.multiline:focus-within {
    padding-top: calc(var(--space-16) - 1px);
}

.input-icon {
    color: var(--icon-muted);
}

.prefix {
    flex-shrink: 0;
    align-self: stretch;
    display: flex;
    align-items: center;
    padding-right: var(--space-16);
    border-right: var(--border-default) solid var(--input);
    color: var(--text-primary);
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
}

input,
textarea {
    flex: 1;
    min-width: 0;
    padding: 0;
    border: none;
    outline: none;
    background: transparent;
    color: var(--text-primary);
    font-family: inherit;
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
    resize: none;
}

input::placeholder,
textarea::placeholder {
    color: var(--text-placeholder);
    font-weight: var(--font-weight-regular);
}

.helper {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-secondary);
}

.helper.error-text {
    color: var(--status-error-foreground);
}
</style>
