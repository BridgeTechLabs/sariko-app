<script>
import { Minus, Plus, ShoppingBasket } from 'lucide-vue-next';
import { useSellerStore } from '@/stores/seller/sellerStore';
import { useCartStore } from '@/stores/cart/cartStore';
import { useAuthStore } from '@/stores/auth/authStore';
import { formatVnd } from '@/utils/priceDisplay';

export default {
    components: { Minus, Plus, ShoppingBasket },

    data() {
        return { loading: false }
    },

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
        quantity() {
            return this.sellerStore.foodQuantity || 1
        },
        canDecrease() {
            return !!this.food && this.quantity > 1
        },
        canAdd() {
            // A dish with levels cannot be priced until one is picked — the backend
            // rejects it anyway, so the button must not offer it.
            const levelPicked = !this.levels.length || !!this.sellerStore.selectedVariantId
            return !!this.food && !!this.seller && levelPicked && !this.loading
        },
        levels() {
            return (this.food?.food_item_variants || []).filter(v => v.is_available !== false)
        },
        selectedVariant() {
            return this.levels.find(v => v.id === this.sellerStore.selectedVariantId) || null
        },
        unitPrice() {
            if (!this.food) return 0
            return this.selectedVariant ? Number(this.selectedVariant.price) : Number(this.food.price)
        },
        singlePriceText() {
            if (!this.food) return '—'
            return formatVnd(this.unitPrice)
        },
        totalPriceText() {
            if (!this.food) return '—'
            return formatVnd(this.unitPrice * this.quantity)
        }
    },

    methods: {
        decrease() {
            if (!this.canDecrease) return
            this.sellerStore.foodQuantity = this.quantity - 1
        },
        increase() {
            if (!this.food) return
            this.sellerStore.foodQuantity = this.quantity + 1
        },
        async addToCart() {
            if (!this.canAdd) return
            const authStore = useAuthStore()
            if (!authStore.user) {
                this.$router.push('/signin')
                return
            }
            this.loading = true
            const cartStore = useCartStore()
            try {
                await cartStore.addItem(this.seller.id, this.food.id, this.seller.store_name, this.quantity, this.sellerStore.selectedVariantId)
                if (cartStore.isShowModalCartConflict) {
                    this.loading = false
                    return
                }
                this.$q.notify({
                    classes: 'quasar-notify-positive',
                    message: `✔️ ${this.$t('food_detail_page.toast_added_to_cart', { name: this.food.name })}`,
                    position: 'bottom',
                    timeout: 1500,
                })
                this.$router.back()
            } finally {
                this.loading = false
            }
        }
    }
}
</script>

<template>
    <div class="action-bar">

        <div class="controls-row">
            <div class="qty-pill" role="group" :aria-label="$t('food_detail_page.label_quantity')">
                <div class="btn-qty-pill-sub">
                    <q-btn
                    dense
                    flat
                    :disabled="!canDecrease"
                    :aria-label="$t('food_detail_page.button_decrease') || 'Decrease quantity'"
                    @click="decrease"
                    >
                        <Minus style="color: white; background-color: black; border-radius: 50%;"/>
                    </q-btn>
                </div>
                <span class="qty-pill__value" aria-live="polite">{{ quantity }}</span>
                <div class="btn-qty-pill-sub">
                    <q-btn
                    dense
                    flat
                    :disabled="!food"
                    :aria-label="$t('food_detail_page.button_increase') || 'Increase quantity'"
                    @click="increase"
                    >
                        <Plus style="color: black; background-color: #f5A623; border-radius: 50%;" />
                    </q-btn>
                </div>
            </div>

            <div class="total-row">
                <div class="total-row__label">{{ $t('food_detail_page.label_total_price') }}</div>
                <div class="price">
                    <div v-if="quantity > 1" class="total-row__price-per-item">{{ singlePriceText }}</div>
                    <div class="total-row__value">{{ totalPriceText }}</div> 
                </div>
            </div>
        </div>


        <button
            class="cta"
            :disabled="!canAdd"
            :aria-busy="loading"
            :aria-label="food
                ? `${$t('food_detail_page.button_add_to_cart')} — ${food.name}`
                : $t('food_detail_page.button_add_to_cart')"
            @click="addToCart"
        >
            <span v-if="loading" class="cta__spinner" aria-hidden="true"></span>
            <ShoppingBasket v-else :size="20" />
            <span class="cta__label">{{ $t('food_detail_page.button_add_to_cart') }}</span>
        </button>
    </div>
</template>

<style lang="scss" scoped>
.action-bar {
    display: flex;
    flex-direction: column;
    gap: 14px;
    width: 100%;
    font-family: $sariko-font-family-secondary;
}

/* Total price row */
.total-row {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: flex-end;
    gap: 12px;  
    padding: 0 4px;
}

.price {
    display: flex;
    align-items: baseline;
}

.total-row__label {
    font-size: 12px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.5);
    letter-spacing: 0.2px;
}

.total-row__price-per-item {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
}

.total-row__value {
    margin-left: 10px;
    font-size: 22px;
    font-weight: 800;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.01em;
    line-height: 1;
}

/* Controls row */
.controls-row {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 12px;
    width: 100%;
}

/* Quantity pill */
.qty-pill {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    flex: 0 0 auto;
    background-color: rgb(255, 255, 255, 0.05);
}

.btn-qty-pill-sub {
    border-radius: 50%;
    cursor: pointer;
    transition: transform 100ms ease, background 160ms ease, opacity 160ms ease;
}

.btn-qty-pill-add {
    border-radius: 50%;
    cursor: pointer;
    transition: transform 100ms ease, background 160ms ease, opacity 160ms ease;
}

.qty-pill__btn:hover {
    background: rgba(255, 255, 255, 0.1);
}

.qty-pill__btn:active {
    transform: scale(0.9);
}

.qty-pill__btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
}

.qty-pill__btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
}

.qty-pill__value {
    min-width: 22px;
    text-align: center;
    font-size: 16px;
    font-weight: 700;
    line-height: 1;
    color: #ffffff;
    font-variant-numeric: tabular-nums;
}

/* CTA */
.cta {
    flex: 1 1 auto;
    height: 56px;
    border-radius: 999px;
    background: var(--color-accent);
    color: var(--bg-main);
    border: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.01em;
    line-height: 1;
    box-shadow: var(--cta-shadow);
    cursor: pointer;
    transition: transform 120ms ease, box-shadow 160ms ease, filter 160ms ease, opacity 160ms ease;
}

.cta:hover {
    filter: brightness(1.05);
}

.cta:active {
    transform: scale(0.98);
    box-shadow: var(--cta-shadow-active);
}

.cta:disabled {
    opacity: 0.55;
    box-shadow: none;
    pointer-events: none;
}

.cta:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 3px;
}

.cta__label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.cta__spinner {
    width: 18px;
    height: 18px;
    border-radius: 999px;
    border: 2px solid rgba(4, 10, 20, 0.25);
    border-top-color: #040A14;
    animation: cta-spin 720ms linear infinite;
}

@keyframes cta-spin {
    to { transform: rotate(360deg); }
}

@media (max-width: 360px) {
    .total-row__value { font-size: 20px; }
    .qty-pill { height: 52px; }
    .qty-pill__btn { width: 34px; height: 34px; }
    .cta { height: 52px; font-size: 14px; }
}

@media (prefers-reduced-motion: reduce) {
    .qty-pill__btn:active,
    .cta:active { transform: none; }
    .cta__spinner { animation-duration: 1.5s; }
}
</style>
