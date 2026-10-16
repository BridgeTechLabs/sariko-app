<script>
import { mapState } from 'pinia'
import { useSearchStore } from '@/stores/search/searchStore'

export default {
    name: 'CategoryResults',
    computed: {
        ...mapState(useSearchStore, ['categoryResults'])
    }
}
</script>

<template>
    <div class="category-results">
        <div class="section-title">Categories ({{ categoryResults.length }})</div>

        <div v-for="(c, i) in categoryResults" :key="`c-${i}`" class="category-row">
            <q-img :src="c.seller.avatar_url" :ratio="1" class="seller-avatar" />
            <div class="info">
                <div class="category-name">{{ c.name }}</div>
                <div class="store-name">{{ c.seller.store_name }}</div>
            </div>
        </div>

        <div v-if="!categoryResults.length" class="empty">{{ $t('search_page.no_category') }}</div>
    </div>
</template>

<style lang="scss" scoped>
.section-title {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.5);
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-family: $sariko-font-family-secondary;
}

.category-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
}

.seller-avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    flex-shrink: 0;
}

.info {
    flex: 1;
    min-width: 0;
}

.category-name {
    font-family: $sariko-font-family-secondary;
    font-size: 14px;
    font-weight: 600;
    color: #fff;
    line-height: 1.3;
    margin-bottom: 2px;
}

.store-name {
    font-family: $sariko-font-family-secondary;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.7);
}

.empty {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.3);
    font-style: italic;
    font-family: $sariko-font-family-secondary;
}
</style>
