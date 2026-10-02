<script>
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';

// Section title + optional supporting line + optional "See all" link (emits `link`).
export default {
    components: { BaseIcon },

    emits: ['link'],

    props: {
        title: {
            type: String,
            required: true,
        },
        sub: {
            type: String,
            default: null,
        },
        linkLabel: {
            type: String,
            default: null,
        },
    },
}
</script>

<template>
    <div class="base-section-head">
        <div class="titles">
            <p class="title">{{ title }}</p>
            <p v-if="sub" class="sub">{{ sub }}</p>
        </div>
        <button v-if="linkLabel" class="link" type="button" @click="$emit('link')">
            <span>{{ linkLabel }}</span>
            <BaseIcon name="chevron-right" :size="16" />
        </button>
    </div>
</template>

<style scoped>
p {
    margin: 0;
}

.base-section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-16);
}

.titles {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-8);
}

.title {
    font-size: var(--font-size-lg);
    line-height: var(--font-line-height-24);
    font-weight: var(--font-weight-semibold);
    letter-spacing: -0.1px;
    color: var(--text-primary);
}

.sub {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-secondary);
}

.link {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: var(--space-8);
    padding: var(--space-8) 0;
    border: none;
    background: none;
    color: var(--text-gold);
    font-family: inherit;
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
    cursor: pointer;
}
</style>
