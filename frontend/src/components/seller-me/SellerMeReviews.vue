<script>
import { Star, User } from 'lucide-vue-next';
import { mapState } from 'pinia';
import StarRating from '@/components/shared/StarRating.vue';
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import apiSellerDashboard from '@/apis/sellers/apiSellerDashboard';
import { formatVnTime } from '@/utils/vnTime';

const PAGE_SIZE = 10

export default {
    name: 'SellerMeReviews',

    components: { Star, User, StarRating },

    // preview > 0: the "Me" page shows only the newest `preview` reviews and a link to the full list
    // (/seller/me/reviews), so it does not grow with every review. 0: full list with "See more".
    props: {
        preview: { type: Number, default: 0 },
    },

    data() {
        return {
            reviews: [],
            loading: true,
            loadingMore: false,
            error: false,
            hasMore: false,
        }
    },

    computed: {
        ...mapState(useDashboardStore, ['sellerInfo']),

        ratingAvg() {
            const avg = this.sellerInfo?.rating_avg
            return avg == null ? null : Number(avg).toFixed(1)
        },

        ratingCount() {
            return this.sellerInfo?.rating_count || 0
        },
    },

    mounted() {
        if (!this.sellerInfo) useDashboardStore().fetchSellerInfo()
        this.load()
    },

    methods: {
        async load() {
            this.loading = true
            this.error = false
            try {
                // preview: ask one more than shown, to know whether there are others
                const limit = this.preview ? this.preview + 1 : PAGE_SIZE
                const res = await apiSellerDashboard.getReviews(limit, 0)
                const page = res.reviews || []
                this.reviews = this.preview ? page.slice(0, this.preview) : page
                this.hasMore = page.length === limit
            } catch (e) {
                console.error('SellerMeReviews - load -', e)
                this.error = true
            } finally {
                this.loading = false
            }
        },

        async loadMore() {
            this.loadingMore = true
            try {
                const res = await apiSellerDashboard.getReviews(PAGE_SIZE, this.reviews.length)
                const page = res.reviews || []
                this.reviews.push(...page)
                this.hasMore = page.length === PAGE_SIZE
            } catch (e) {
                console.error('SellerMeReviews - loadMore -', e)
            } finally {
                this.loadingMore = false
            }
        },

        // The API masks the name and returns null when there is none.
        displayName(review) {
            return review.reviewer_name || this.$t('food_detail_page.review_anonymous')
        },

        dateText(value) {
            return formatVnTime(value, { day: '2-digit', month: '2-digit', year: 'numeric' })
        },
    },
}
</script>

<template>
    <div>
        <div v-if="preview" class="section-title">{{ $t('seller_me.section_title_reviews') }}</div>
        <div class="reviews-card">

            <template v-if="loading">
                <q-skeleton type="text" width="40%" animation="pulse" />
                <q-skeleton type="text" width="80%" animation="pulse" />
                <q-skeleton type="text" width="70%" animation="pulse" />
            </template>

            <div v-else-if="error" class="reviews-state">
                <div class="reviews-state-text">{{ $t('seller_me.reviews_load_error') }}</div>
                <q-btn flat no-caps dense class="reviews-btn" :label="$t('seller_me.reviews_retry')" @click="load" />
            </div>

            <div v-else-if="!reviews.length" class="reviews-state">
                <Star :size="28" class="reviews-icon" />
                <div class="reviews-state-text">{{ $t('seller_me.reviews_empty') }}</div>
                <div class="reviews-state-sub">{{ $t('seller_me.reviews_empty_sub') }}</div>
            </div>

            <template v-else>
                <div v-if="ratingAvg" class="reviews-summary">
                    <span class="reviews-avg">{{ ratingAvg }}</span>
                    <Star :size="18" class="reviews-avg-star" />
                    <span class="reviews-count">{{ $t('seller_me.reviews_count', { n: ratingCount }, ratingCount) }}</span>
                </div>

                <div v-for="review in reviews" :key="review.id" class="review">
                    <q-avatar size="32px" class="review-avatar">
                        <img v-if="review.reviewer_avatar_url" :src="review.reviewer_avatar_url" />
                        <User v-else :size="16" />
                    </q-avatar>

                    <div class="review-body">
                        <div class="review-head">
                            <span class="review-name">{{ displayName(review) }}</span>
                            <span class="review-date">{{ dateText(review.created_at) }}</span>
                        </div>
                        <StarRating :model-value="review.rating" :size="13" :gap="2" readonly />
                        <p v-if="review.comment" class="review-comment">{{ review.comment }}</p>
                        <div v-for="item in review.items" :key="item.id" class="review-item">
                            <div class="review-meta">
                                <StarRating :model-value="item.rating" :size="11" :gap="2" readonly />
                                <span class="review-dish">{{ item.name_snapshot }}</span>
                                <span v-if="!item.food_item_id" class="review-dish-deleted">{{ $t('seller_me.reviews_dish_deleted') }}</span>
                            </div>
                            <p v-if="item.comment" class="review-comment">{{ item.comment }}</p>
                        </div>
                    </div>
                </div>

                <q-btn v-if="hasMore && preview" flat no-caps dense class="reviews-btn" to="/seller/me/reviews"
                    :label="$t('seller_me.reviews_see_all')" />
                <q-btn v-else-if="hasMore" flat no-caps dense class="reviews-btn" :loading="loadingMore"
                    :label="$t('seller_me.reviews_more')" @click="loadMore" />
            </template>

        </div>
    </div>
</template>

<style scoped>
.section-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
    padding-left: 4px;
}

.reviews-card {
    background: rgb(255, 255, 255, 0.05);
    border-radius: 16px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}

.reviews-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 8px 0;
}

.reviews-icon {
    color: var(--color-accent);
    opacity: 0.6;
    margin-bottom: 4px;
}

.reviews-state-text {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
}

.reviews-state-sub {
    font-size: 13px;
    color: var(--text-secondary);
    text-align: center;
}

.reviews-btn {
    align-self: center;
    color: var(--color-accent);
    font-weight: 600;
}

.reviews-summary {
    display: flex;
    align-items: center;
    gap: 6px;
}

.reviews-avg {
    font-size: 22px;
    font-weight: 700;
    color: var(--text-primary);
}

.reviews-avg-star {
    color: #facc15;
    fill: #facc15;
}

.reviews-count {
    font-size: 13px;
    color: var(--text-secondary);
}

.review {
    display: flex;
    gap: 10px;
}

.review-avatar {
    flex-shrink: 0;
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-secondary);
}

.review-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.review-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
}

.review-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.review-date {
    flex-shrink: 0;
    font-size: 12px;
    color: var(--text-muted);
}

.review-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
}

.review-dish {
    font-size: 12px;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.review-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding-left: 10px;
    border-left: 2px solid rgba(255, 255, 255, 0.08);
}

.review-dish-deleted {
    flex-shrink: 0;
    font-size: 11px;
    color: var(--text-muted);
}

.review-comment {
    margin: 0;
    font-size: 13px;
    color: var(--text-primary);
    white-space: pre-line;
    overflow-wrap: anywhere;
}
</style>
