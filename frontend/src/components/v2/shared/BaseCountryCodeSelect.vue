<script>
import { getPhoneCountries, flagUrl, dialCodeOf } from '@/utils/countries';
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';
import BaseIconButton from '@/components/v2/shared/BaseIconButton.vue';

// Phone country code picker, use with v-model (ISO code, e.g. 'VN') in BaseTextField's `leading` slot.
// Trigger matches BaseTextField's `prefix`; the list opens in a bottom sheet with search.
// Not in Figma — sheet styling is built from the v2 tokens.
const normalize = (text) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

export default {
    components: { BaseIcon, BaseIconButton },

    emits: ['update:modelValue'],

    props: {
        modelValue: {
            type: String,
            default: 'VN',
        },
    },

    data() {
        return {
            isOpen: false,
            query: '',
        }
    },

    computed: {
        flag() {
            return flagUrl(this.modelValue)
        },

        dialCode() {
            return dialCodeOf(this.modelValue)
        },

        countries() {
            return getPhoneCountries(this.$i18n.locale)
        },

        filteredCountries() {
            const query = normalize(this.query.trim())
            if (!query) return this.countries
            const digits = query.replace(/\D/g, '')
            return this.countries.filter(c =>
                normalize(c.name).includes(query)
                || c.iso.toLowerCase() === query
                || (digits && c.dialCode.slice(1).startsWith(digits))
            )
        },
    },

    methods: {
        onClickedCountry(iso) {
            this.$emit('update:modelValue', iso)
            this.isOpen = false
        },
    },
}
</script>

<template>
    <!-- span, not button: inside BaseTextField's <label> a button before the input would become the labelled
         control; .prevent stops the label from also focusing the input -->
    <span
        class="trigger"
        role="button"
        tabindex="0"
        :aria-label="$t('account_v2.country_code_title')"
        @click.prevent="isOpen = true"
        @keydown.enter.prevent="isOpen = true"
        @keydown.space.prevent="isOpen = true"
    >
        <img v-if="flag" class="flag" :src="flag" alt="" width="20" height="15" />
        <span>{{ dialCode }}</span>
        <BaseIcon class="chevron" name="chevron-down" :size="16" />
    </span>

    <q-dialog v-model="isOpen" position="bottom" full-width @hide="query = ''">
        <div class="sheet">
            <div class="sheet-head">
                <p class="sheet-title">{{ $t('account_v2.country_code_title') }}</p>
                <BaseIconButton icon="x" :size="36" :label="$t('account_v2.country_code_close')" @click="isOpen = false" />
            </div>

            <label class="search">
                <BaseIcon class="search-icon" name="search" :size="20" />
                <input
                    v-model="query"
                    type="search"
                    autocomplete="off"
                    :placeholder="$t('account_v2.country_code_search')"
                />
            </label>

            <ul v-if="filteredCountries.length" class="list">
                <li v-for="country in filteredCountries" :key="country.iso">
                    <button
                        class="row"
                        :class="{ selected: country.iso === modelValue }"
                        type="button"
                        @click="onClickedCountry(country.iso)"
                    >
                        <img v-if="country.flag" class="flag" :src="country.flag" alt="" width="24" height="18" loading="lazy" />
                        <span class="name">{{ country.name }}</span>
                        <span class="dial">{{ country.dialCode }}</span>
                        <BaseIcon v-if="country.iso === modelValue" class="check" name="check" :size="20" />
                    </button>
                </li>
            </ul>
            <p v-else class="empty">{{ $t('account_v2.country_code_empty') }}</p>
        </div>
    </q-dialog>
</template>

<style scoped>
p {
    margin: 0;
}

/* Same look as BaseTextField .prefix */
.trigger {
    flex-shrink: 0;
    align-self: stretch;
    display: flex;
    align-items: center;
    gap: var(--space-8);
    padding: 0 var(--space-16) 0 0;
    border-right: var(--border-default) solid var(--input);
    color: var(--text-primary);
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
    cursor: pointer;
}

.flag {
    flex-shrink: 0;
    border-radius: 2px;
    object-fit: cover;
}

.chevron {
    color: var(--icon-muted);
}

.sheet {
    height: 80vh;
    height: 80dvh;
    display: flex;
    flex-direction: column;
    gap: var(--space-16);
    padding: var(--space-16) var(--space-24) 0;
    background: var(--card);
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
    font-family: var(--font-family-sans);
}

.sheet-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-16);
}

.sheet-title {
    font-size: var(--font-size-lg);
    line-height: var(--font-line-height-24);
    font-weight: var(--font-weight-semibold);
    letter-spacing: -0.005em;
    color: var(--text-primary);
}

.search {
    display: flex;
    align-items: center;
    gap: var(--space-8);
    padding: var(--space-16);
    background: var(--background);
    border: var(--border-default) solid var(--input);
    border-radius: var(--radius-lg);
}

/* 2px border on focus — shrink padding by 1px so content doesn't shift */
.search:focus-within {
    border-width: var(--border-strong);
    border-color: var(--ring);
    padding: calc(var(--space-16) - 1px);
}

.search-icon {
    color: var(--icon-muted);
}

.search input {
    flex: 1;
    min-width: 0;
    padding: 0;
    border: none;
    outline: none;
    background: transparent;
    color: var(--text-primary);
    font-family: inherit;
    font-size: var(--font-size-base);
    line-height: var(--font-line-height-24);
}

.search input::placeholder {
    color: var(--text-placeholder);
}

.list {
    flex: 1;
    min-height: 0;
    margin: 0 calc(-1 * var(--space-24));
    padding: 0 0 max(var(--space-24), env(safe-area-inset-bottom, 0px));
    overflow-y: auto;
    list-style: none;
}

.row {
    width: 100%;
    display: flex;
    align-items: center;
    gap: var(--space-16);
    padding: var(--space-16) var(--space-24);
    border: none;
    border-bottom: var(--border-default) solid var(--divider);
    background: transparent;
    color: var(--text-primary);
    font-family: inherit;
    font-size: var(--font-size-base);
    line-height: var(--font-line-height-24);
    text-align: left;
    cursor: pointer;
}

.row.selected {
    background: var(--secondary);
    font-weight: var(--font-weight-semibold);
}

.name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.dial {
    color: var(--text-secondary);
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
}

.check {
    color: var(--icon-default);
}

.empty {
    padding: var(--space-24) 0;
    text-align: center;
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-secondary);
}
</style>
