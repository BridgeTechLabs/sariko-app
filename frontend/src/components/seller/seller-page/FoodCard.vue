<script>
import { blockedByClosedStore } from '@/utils/storeOpen';
import { Star } from 'lucide-vue-next';
import { mapState } from 'pinia';
import { useSellerStore } from '@/stores/seller/sellerStore';
import { useCartStore } from '@/stores/cart/cartStore';
import { useAuthStore } from '@/stores/auth/authStore';

export default {
    props: {
        // false = seller switched "Đang bán" off: shown as Sold out, not tappable (deleted dishes aren't returned at all)
        isAvailable: {
            type: Boolean,
            default: true
        },
        hasVariants: {
            type: Boolean,
            default: false
        },
        itemId: {
            required: true,
            type: String
        },
        name: {
            required: true,
            type: String
        },
        price: {
            required: true,
            type: String
        },
        imgSrc: {
            required: true,
            type: String
        },
        unitLabel: {
            type: String,
            default: null
        },
        preorderDay: {
            type: Number,
            default: 0
        },
        ratingAvg: {
            type: Number,
            default: null
        },
        ratingCount: {
            type: Number,
            default: 0
        },
        // Portions left today (utils/portions.js); null = not shown. 0 = sold out today, not tappable
        portionsLeft: {
            type: Number,
            default: null
        }
    },

    components: {
        Star
    },

    data() {
        return {
            loading: false
        }
    },

    computed: {
        ...mapState(useSellerStore, ['seller']),
        // Nothing is shown until a dish has been rated — an empty star row reads as
        // "rated badly" rather than "not rated yet".
        storeClosed() {
            return blockedByClosedStore(this.seller, this.preorderDay)
        },
        hasRating() {
            return this.ratingCount > 0 && this.ratingAvg != null
        },
        canOrder() {
            return this.isAvailable && this.portionsLeft !== 0
        }
    },

    methods: {
        goToDetail() {
            if (!this.canOrder) return
            if (this.seller?.slug) {
                this.$router.push(`/food/${this.seller.slug}/${this.itemId}`)
            }
        },

        async handleAddToCart(e) {
            e.stopPropagation()
            if (!this.canOrder) return
            // No single price to add — the level is picked on the detail page.
            if (this.hasVariants) return this.goToDetail()
            const authStore = useAuthStore()
            if (!authStore.user) {
                this.$router.push('/signin')
                return
            }
            if (this.loading) return
            this.loading = true
            const cartStore = useCartStore()
            const added = await cartStore.addItem(this.seller.id, this.itemId, this.seller.store_name)
            this.loading = false
            if (added && !cartStore.isShowModalCartConflict) {
                this.$q.notify({
                    classes: 'quasar-notify-positive',
                    message: `✔️ ${this.name} added to cart`,
                    progress: true,
                    position: 'bottom',
                    timeout: 1500,
                })
            }
        }
    }
}
</script>

<template>
    <div class="food-row" :class="{ 'sold-out': !canOrder }" @click="goToDetail">

        <div class="thumb-wrap">
            <img
            :src="imgSrc"
            :alt="name"
            class="food-thumb"
            @error="$event.target.src = '/images/default-food-image.webp'"
            />
            <div v-if="!canOrder" class="sold-out-label">{{ isAvailable ? $t('seller_page.section_food_cards.label_sold_out_today') : $t('seller_page.section_food_cards.label_sold_out') }}</div>
        </div>

        <div class="food-info">
            <div class="food-name">
                <div class="food-name__label">{{ name }}</div>
                <div v-if="hasRating" class="food-name__review">
                    <Star size="12px" fill="gold" color="gold" style="margin-right: 4px;"/>
                    <div class="text-yellow">{{ ratingAvg }}</div>
                    <div class="review-count">({{ ratingCount }})</div>
                </div>
            </div>

            <div class="badge-row">
                <q-badge v-if="preorderDay > 0" class="preorder-badge" color="amber-8">
                    {{ $t('seller_page.section_food_cards.lable_item_pre_order') }}: {{ preorderDay }} {{ $t('seller_page.section_food_cards.lable_item_pre_order_unit_day') }}
                </q-badge>
                <q-badge v-else class="preorder-badge" color="positive">
                    {{ $t('seller_page.section_food_cards.label_item_instant') }}
                </q-badge>
                <q-badge v-if="portionsLeft > 0" class="preorder-badge" color="grey-8">
                    {{ $t('seller_page.section_food_cards.label_portions_left', { n: portionsLeft }) }}
                </q-badge>
            </div>

            <div class="price-row">
                <div class="price-row__text">
                    <div class="food-price">{{ price }}</div>
                    <div v-if="unitLabel" class="unit-label">/ {{ unitLabel }}</div>
                </div>
                <q-btn flat dense no-caps :loading="loading" :disable="storeClosed || !canOrder" @click="handleAddToCart">
                    <q-icon name="fa-solid fa-circle-plus" size="26px" style="color: #f5A623" />
                    <template #loading>
                        <q-spinner-dots color="orange" size="20px" />
                    </template>
                </q-btn>
            </div>
        </div>
    </div>
</template>

<style lang="scss" scoped>

.food-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    font-family: $sariko-font-family-secondary;
    cursor: pointer;

    &:last-child {
        border-bottom: none;
    }

    &:active {
        background: rgba(255, 255, 255, 0.03);
    }
}

.food-thumb {
    /* matches the 3-line text column height, so the photo fills the row instead of
       leaving dead vertical space beside it */
    width: 96px;
    height: 96px;
    flex-shrink: 0;
    border-radius: 12px;
    object-fit: cover;
    background: rgba(255, 255, 255, 0.05);
}

.food-info {
    flex: 1;
    min-width: 0;
}

.food-name {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 700;
}

.food-name__label {
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.food-name__review {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    font-size: 12px;
}

/* Bare number, no word: "4.9 (12)" is the compact form people read everywhere. */
.review-count {
    margin-left: 3px;
    font-weight: 500;
    color: var(--text-secondary);
}

.badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 5px;
}

.preorder-badge {
    font-size: 10px;
    color: black;
}

.price-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 4px;
}

.price-row__text {
    display: flex;
    align-items: baseline;
    gap: 4px;
}

.food-price {
    font-weight: 600;
    color: var(--text-active);
}

.unit-label {
    font-size: 11px;
    font-weight: 400;
    color: var(--text-secondary);
}


.thumb-wrap {
    position: relative;
    flex-shrink: 0;
}

// Muted row; the label sits outside the muted parts so it stays readable
.sold-out {
    cursor: default;

    .food-thumb { filter: grayscale(1); opacity: 0.45; }
    .food-info { opacity: 0.45; }
}

.sold-out-label {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    background: rgba(0, 0, 0, 0.45);
    color: #fff;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    text-align: center;
}
</style>
