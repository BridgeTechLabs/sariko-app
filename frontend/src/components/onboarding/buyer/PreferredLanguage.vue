<script>
import { useAuthStore } from '@/stores/auth/authStore';
import { Languages } from 'lucide-vue-next';
import { mapState, mapWritableState } from 'pinia';
import { useAttrs } from 'vue';

export default {
    components: {
        Languages
    },

    computed: {
        ...mapWritableState(useAuthStore, [
            "selectedPreferedLanguage"
        ])
    }
}
</script>

<template>

    <div class="title">
        <Languages class="icon-language"/> <span>{{ $t('onboarding_page.buyer.section_preferred_language.title') }}</span>
    </div>
    <div class="button-groups">
        <div 
        :class="{'language-option': true, 'language-option-active': selectedPreferedLanguage === 'English'}" 
        v-on:click="selectedPreferedLanguage='English'"
        >
            English
        </div>

        <div 
        :class="{'language-option': true, 'language-option-active': selectedPreferedLanguage === 'Fillipino'}" 
        v-on:click="selectedPreferedLanguage='Fillipino'"
        >
            Filipino
        </div>

        <div 
        :class="{'language-option': true, 'language-option-active': selectedPreferedLanguage === 'Tiếng Việt'}" 
        v-on:click="selectedPreferedLanguage='Tiếng Việt'"
        >
            Tiếng Việt
        </div>
    </div>

</template>

<style lang="scss" scoped>
.title {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
}

.icon-language {
    margin-right: 10px;
}

.button-groups {
    display: flex;
}

.language-option {
    display: flex;
    align-items: center;
    background-color: var(--bg-surface);
    margin-right: 10px;
    padding: 5px 30px;
    border-radius: 1rem;
    font-size: 11px;
    font-weight: 600;
}

.language-option-active {
    color: var(--text-active);
    background-color: var(--accent-dim);
    border: 1px solid var(--text-active);
}

</style>