<script>
import { Store, Star } from 'lucide-vue-next';
import FoodOptions from '@/components/food-detail/FoodOptions.vue';
import { useSellerStore } from '@/stores/seller/sellerStore';
import { foodPriceDisplay } from '@/utils/priceDisplay';
import { portionsLeftToday, preorderPortions } from '@/utils/portions';
import { ratingText } from '@/utils/rating';

export default {
    components: { Store, Star, FoodOptions },

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
            return this.sellerStore.foodLevels
        },
        hasRating() {
            return this.food?.rating_count > 0 && this.food?.rating_avg != null
        },
        portionsLeft() {
            return portionsLeftToday(this.food)
        },
        preorderLeft() {
            return preorderPortions(this.food)
        }
    },

    methods: {
        ratingText,
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
                <span class="rating-value">{{ ratingText(food.rating_avg) }}</span>
                <span class="rating-count">
                    ({{ $t('common.rating_count', food.rating_count, { count: food.rating_count }) }})
                </span>
            </div>
            <div class="item-badge">
                <q-badge v-if="food.preorder_day > 0" color="amber-8" class="preorder-badge">
                    {{ $t('seller_page.section_food_cards.lable_item_pre_order') }}: {{ food.preorder_day }} {{ $t('seller_page.section_food_cards.lable_item_pre_order_unit_day') }}
                </q-badge>
                <q-badge v-else class="preorder-badge" color="positive">
                    {{ $t('seller_page.section_food_cards.label_item_instant') }}
                </q-badge>
                <q-badge v-if="portionsLeft > 0" class="preorder-badge" color="grey-8">
                    {{ $t('seller_page.section_food_cards.label_portions_left', { n: portionsLeft }) }}
                </q-badge>
                <q-badge v-else-if="preorderLeft" class="preorder-badge" color="grey-8">
                    {{ $t('seller_page.section_food_cards.label_portions_left_on', preorderLeft) }}
                </q-badge>
            </div>
            <div v-if="seller" class="seller-chip" @click="goToSeller">
                <Store :size="14" style="margin-right: 5px;" />
                <span>{{ seller.store_name || seller.name }}</span>
            </div>
            <span class="food-price">{{ priceText }}</span>

            <FoodOptions />
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
