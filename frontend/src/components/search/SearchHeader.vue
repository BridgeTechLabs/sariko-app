<script>
import { useSearchStore } from '@/stores/search/searchStore'
import { ArrowLeft } from 'lucide-vue-next'

export default {
    name: 'SearchHeader',
    components: { ArrowLeft },
    computed: {
        query: {
            get() { return useSearchStore().query },
            set(value) { useSearchStore().setQuery(value) }
        }
    }
}
</script>

<template>
    <div class="search-header">
        <button class="back-btn" @click="$router.back()">
            <ArrowLeft :size="20" />
        </button>
        <input v-model="query" class="search-input" :placeholder="$t('home_page.section_search_bar.placeholder')" />
    </div>
</template>

<style lang="scss" scoped>
.search-header {
    display: flex;
    align-items: center;
    gap: 12px;
}

.back-btn {
    background: transparent;
    border: none;
    color: #fff;
    cursor: pointer;
    padding: 4px;
    display: flex;
    align-items: center;
}

.search-input {
    flex: 1;
    background: #151b2a;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 8px 12px;
    color: #fff;
    font-size: 14px;
    font-family: $sariko-font-family-secondary;
    outline: none;
}
</style>
