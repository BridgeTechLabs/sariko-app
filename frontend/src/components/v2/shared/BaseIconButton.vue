<script>
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';

// Round icon-only button. `surface` is what it sits on: card → tinted bg, photo/dark header → card bg.
export default {
    components: { BaseIcon },

    props: {
        icon: {
            type: String,
            required: true,
        },
        label: {
            type: String,
            required: true,
        },
        size: {
            type: Number,
            default: 40,
            validator: (value) => [40, 36].includes(value),
        },
        surface: {
            type: String,
            default: 'card',
            validator: (value) => ['card', 'photo'].includes(value),
        },
    },
}
</script>

<template>
    <button
        class="base-icon-button"
        :class="[surface, `size-${size}`]"
        type="button"
        :aria-label="label"
    >
        <BaseIcon :name="icon" :size="size === 40 ? 20 : 18" />
    </button>
</template>

<style scoped>
.base-icon-button {
    flex-shrink: 0;
    padding: 0;
    border: none;
    border-radius: var(--radius-full);
    color: var(--icon-default);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.size-40 {
    width: 40px;
    height: 40px;
}

.size-36 {
    width: 36px;
    height: 36px;
}

.card {
    background: var(--secondary);
}

.photo {
    background: var(--card);
}
</style>
