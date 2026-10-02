<script>
import { mapState, mapActions } from 'pinia';
import { useAccountV2Store, LANGUAGE_OPTIONS_V2 } from '@/stores/v2/account/accountStore';

export default {
    data() {
        return {
            options: LANGUAGE_OPTIONS_V2,
        }
    },

    computed: {
        ...mapState(useAccountV2Store, ['selectedLanguage']),
    },

    mounted() {
        this.fetchAccount()
    },

    methods: {
        ...mapActions(useAccountV2Store, ['fetchAccount', 'selectLanguage']),
    },
}
</script>

<template>
    <div class="options" role="radiogroup" :aria-label="$t('account_v2.language_title')">
        <button
            v-for="option in options"
            :key="option.id"
            class="option"
            :class="{ selected: option.id === selectedLanguage }"
            type="button"
            role="radio"
            :aria-checked="option.id === selectedLanguage"
            @click="selectLanguage(option.id)"
        >
            <span class="code">{{ option.code }}</span>
            <span class="texts">
                <span class="name">{{ $t(`account_v2.language_${option.id}_name`) }}</span>
                <span class="desc">{{ $t(`account_v2.language_${option.id}_desc`) }}</span>
            </span>
            <span class="radio">
                <span v-if="option.id === selectedLanguage" class="dot" />
            </span>
        </button>
    </div>
</template>

<style scoped>
.options {
    display: flex;
    flex-direction: column;
    gap: var(--space-8);
}

.option {
    width: 100%;
    display: flex;
    align-items: center;
    gap: var(--space-16);
    padding: var(--space-16);
    background: var(--card);
    border: var(--border-default) solid var(--border);
    border-radius: var(--radius-xl);
    font-family: var(--font-family-sans);
    text-align: left;
    cursor: pointer;
}

/* Thicker border on selected — trim padding by the extra 1px so content doesn't shift */
.option.selected {
    border: var(--border-strong) solid var(--primary);
    padding: calc(var(--space-16) - (var(--border-strong) - var(--border-default)));
}

.code {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-lg);
    background: var(--secondary);
    color: var(--text-primary);
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-bold);
    letter-spacing: 0.06em;
}

.selected .code {
    background: var(--primary);
    color: var(--primary-foreground);
}

.texts {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
}

.name {
    font-size: var(--font-size-base);
    line-height: var(--font-line-height-24);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.desc {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-secondary);
}

.radio {
    flex-shrink: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: var(--border-strong) solid var(--border);
    border-radius: var(--radius-full);
}

.selected .radio {
    border-color: var(--primary);
}

.dot {
    width: 12px;
    height: 12px;
    border-radius: var(--radius-full);
    background: var(--primary);
}
</style>
