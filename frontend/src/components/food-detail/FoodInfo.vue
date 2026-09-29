<script>
import { Store, Star } from 'lucide-vue-next';
import { useSellerStore } from '@/stores/seller/sellerStore';
import { foodPriceDisplay, formatVnd } from '@/utils/priceDisplay';

export default {
    components: { Store, Star },

    computed: {
        sellerStore() {
            return useSellerStore()
        },
        food() {
            return this.sellerStore.currentFood
        },
        seller() {
            return this.sellerStore.currentSeller
        },
        priceText() {
            if (!this.food) return ''
            // With levels this is a range and a unit suffix would misread
            // ("50.000 ₫ – 80.000 ₫ / phần" suggests one price per unit).
            const base = foodPriceDisplay(this.food)
            if (this.levels.length) return base
            return this.food.unit_label ? `${base} / ${this.food.unit_label}` : base
        },
        levels() {
            return (this.food?.food_item_variants || []).filter(v => v.is_available !== false)
        },
        selectedVariantId() {
            return this.sellerStore.selectedVariantId
        },
        hasRating() {
            return this.food?.rating_count > 0 && this.food?.rating_avg != null
        }
    },

    methods: {
        formatVnd,
        selectVariant(id) {
            this.sellerStore.selectedVariantId = id
        },
        goToSeller() {
            if (this.seller?.slug) {
                this.$router.push(`/seller/${this.seller.slug}`)
            }
        }
    }
}
</script>

<template>
    <div class="food-info">
        <template v-if="food">
            <div class="food-name">{{ food.name }}</div>
            <div v-if="hasRating" class="food-rating">
                <Star :size="15" fill="#f5A623" color="#f5A623" />
                <span class="rating-value">{{ food.rating_avg }}</span>
                <span class="rating-count">
                    ({{ $t('common.rating_count', food.rating_count, { count: food.rating_count }) }})
                </span>
            </div>
            <div class="item-badge">
                <q-badge class="preorder-badge" color="positive"> 
                    {{ $t('seller_page.section_food_cards.label_item_available') }}
                </q-badge>
                <q-badge v-if="food.preorder_day > 0" color="amber-8" class="preorder-badge">
                    {{ $t('seller_page.section_food_cards.lable_item_pre_order') }}: {{ food.preorder_day }} {{ $t('seller_page.section_food_cards.lable_item_pre_order_unit_day') }}
                </q-badge>
            </div>
            <div v-if="seller" class="seller-chip" @click="goToSeller">
                <Store :size="14" style="margin-right: 5px;" />
                <span>{{ seller.store_name || seller.name }}</span>
            </div>
            <span class="food-price">{{ priceText }}</span>

            <div v-if="levels.length" class="level-picker">
                <div class="level-label">{{ $t('food_detail_page.label_choose_option') }}</div>
                <div class="level-chips">
                    <button
                        v-for="v in levels"
                        :key="v.id"
                        class="level-chip"
                        :class="{ 'level-chip--on': v.id === selectedVariantId }"
                        :aria-pressed="v.id === selectedVariantId"
                        @click="selectVariant(v.id)"
                    >
                        <span class="level-chip__name">{{ v.name }}</span>
                        <span class="level-chip__price">{{ formatVnd(v.price) }}</span>
                    </button>
                </div>
            </div>
            <p v-if="food.description" class="food-description">{{ food.description }}</p>
        </template>

        <template v-else>
            <q-skeleton type="text" width="70%" height="28px" animation="pulse" />
            <q-skeleton type="text" width="40%" height="24px" animation="pulse" class="q-mt-sm" />
            <q-skeleton type="text" width="50%" height="18px" animation="pulse" class="q-mt-md" />
            <q-skeleton type="text" width="100%" animation="pulse" class="q-mt-md" />
            <q-skeleton type="text" width="90%" animation="pulse" />
            <q-skeleton type="text" width="60%" animation="pulse" />
        </template>
    </div>
</template>

<style lang="scss" scoped>
.food-info {
    display: flex;
    flex-direction: column;
}

.level-picker {
    margin-top: 12px;
}

.level-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted, #9aa3b2);
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-bottom: 8px;
}

.level-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.level-chip {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    padding: 8px 14px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: transparent;
    color: inherit;
    cursor: pointer;
    font-family: inherit;

    &__name { font-size: 14px; font-weight: 600; }
    &__price { font-size: 12px; opacity: 0.75; }

    &--on {
        border-color: #f5A623;
        background: rgba(245, 166, 35, 0.12);
        .level-chip__price { opacity: 1; color: #f5A623; }
    }
}

.food-name {
    font-size: 22px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.3;
    margin-bottom: 10px;
}

.food-rating {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 12px;
}

.rating-value {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-active);
}

.rating-count {
    font-size: 13px;
    color: var(--text-secondary);
}

.item-badge {
    margin-bottom: 20px;
}

.food-price {
    display: block;
    font-size: 24px;
    font-weight: 800;
    color: var(--text-active);
    margin-bottom: 10px;
}

.preorder-badge {
    font-size: 10px;
    color: black; 
    margin-right: 5px;
}

.seller-chip {
    display: flex;
    width: fit-content;
    align-items: baseline;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-active);
    background: var(--accent-dim);
    padding: 6px 12px;
    border-radius: 999px;
    margin-bottom: 18px;
    cursor: pointer;
    transition: transform 0.15s ease;
}

.seller-chip:active {
    transform: scale(0.97);
}

.food-description {
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 1.6;
    white-space: pre-line;
}
</style>
