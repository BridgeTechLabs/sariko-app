<script>
import { mapState } from 'pinia'
import { useSearchStore } from '@/stores/search/searchStore'

export default {
    name: 'FoodResults',
    computed: {
        ...mapState(useSearchStore, ['foodResults'])
    },
    methods: {
        goToDetail(f) {
            this.$router.push({
                name: 'food-detail',
                params: { sellerSlug: f.seller.slug, foodId: f.id }
            })
        }
    }
}
</script>

<template>
    <div class="food-results">
        <div class="section-title">Foods ({{ foodResults.length }})</div>

        <div v-for="(f, i) in foodResults" :key="`f-${i}`" class="food-row">
            <div class="food-image-wrap">
                <q-img :src="f.image_url" :ratio="2.9/1" class="food-image clickable" @click="goToDetail(f)" />
                <div v-if="f.preorder_day > 0" class="preorder-badge">
                    PRE-ORDER · {{ f.preorder_day }} {{ f.preorder_day === 1 ? 'day' : 'days' }}
                </div>
            </div>

            <div class="info">
                <div class="title-row">
                    <span class="food-name clickable" @click="goToDetail(f)">{{ f.name }}</span>
                    <span class="title-sep">•</span>
                    <span class="category">{{ f.category }}</span>
                </div>
                <div class="meta-row">
                    <span class="store-name">{{ f.seller.store_name }}</span>
                </div>
            </div>
        </div>

        <div v-if="!foodResults.length" class="empty">{{ $t('search_page.no_food') }}</div>
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

.food-row {
    margin-bottom: 38px;
}

.food-image-wrap {
    position: relative;
}

.food-image {
    width: 100%;
    border-radius: 12px;
    overflow: hidden;
}

.clickable {
    cursor: pointer;
}

.preorder-badge {
    position: absolute;
    top: 8px;
    left: 8px;
    background: rgba(0, 0, 0, 0.72);
    color: #facc15;
    font-family: $sariko-font-family-secondary;
    font-size: 10px;
    font-weight: 700;
    padding: 4px 8px;
    border-radius: 6px;
    letter-spacing: 0.5px;
    pointer-events: none;
}

.info {
    margin-top: 15px;
    padding: 0 2px;
}

.title-row {
    display: flex;
    align-items: baseline;
    gap: 6px;
    margin-bottom: 4px;
    min-width: 0;
}

.food-name {
    font-family: $sariko-font-family-secondary;
    font-size: 15px;
    font-weight: 600;
    color: #fff;
    line-height: 1.3;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
}

.category {
    font-family: $sariko-font-family-secondary;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.6);
    white-space: nowrap;
    flex-shrink: 0;
}

.title-sep {
    color: rgba(255, 255, 255, 0.5);
    flex-shrink: 0;
    font-size: 10px;
}

.meta-row {
    display: flex;
    align-items: center;
    gap: 4px;
    font-family: $sariko-font-family-secondary;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.6);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.empty {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.3);
    font-style: italic;
    font-family: $sariko-font-family-secondary;
}
</style>
