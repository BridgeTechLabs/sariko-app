<script>
import { useCartStore } from '@/stores/cart/cartStore';
import { useAuthStore } from '@/stores/auth/authStore';
import { CirclePlus } from 'lucide-vue-next';

export default {
    name: 'FeaturedDishCard',
    components: { CirclePlus },
    props: {
        hasVariants: {
            type: Boolean,
            default: false
        },
        // Stock under the dish's minimum: shown as sold out, not tappable, like on the store page
        soldOut: {
            type: Boolean,
            default: false
        },
        itemId: {
            required: true,
            type: [String, Number]
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
        sellerSlug: {
            required: true,
            type: String
        },
        sellerId: {
            required: true,
            type: String
        },
        sellerName: {
            required: true,
            type: String
        }
    },

    data() {
        return {
            loading: false
        }
    },

    methods: {
        goToDetail() {
            if (this.soldOut) return
            this.$router.push(`/food/${this.sellerSlug}/${this.itemId}`)
        },

        async handleAddToCart(e) {
            e.stopPropagation()
            if (this.soldOut) return
            // No single price to add — the level / options are picked on the detail page.
            if (this.hasVariants) return this.goToDetail()
            const authStore = useAuthStore()
            if (!authStore.user) {
                this.$router.push('/signin')
                return
            }
            if (this.loading) return
            this.loading = true
            const cartStore = useCartStore()
            const added = await cartStore.addItem(this.sellerId, this.itemId, this.sellerName)
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
    <div class="card" @click="goToDetail">

        <div class="food-image">
            <q-img
            :src="imgSrc"
            :ratio="16/9"
            :class="{ 'sold-out-img': soldOut }"
            />
            <div v-if="soldOut" class="sold-out-label">{{ $t('seller_page.section_food_cards.label_sold_out') }}</div>
        </div>

        <div class="food-info">
            <div class="food-name">{{ name }}</div>
            <div class="seller-name">{{ sellerName }}</div>
            <div class="price-row">
                <div class="food-price">{{ price }}</div>
                <q-btn v-if="!soldOut" flat dense no-caps :loading="loading" @click="handleAddToCart">
                    <CirclePlus :size="22" style="color: #f5A623" />
                    <template #loading>
                        <q-spinner-dots color="orange" size="16px" />
                    </template>
                </q-btn>
            </div>
        </div>
    </div>
</template>

<style lang="scss" scoped>

.food-image { position: relative; }

.sold-out-img { opacity: 0.4; }

.sold-out-label {
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    padding: 3px 10px;
    border-radius: 8px;
    background: rgba(0, 0, 0, 0.7);
    color: #fff;
    font-size: 11px;
    font-weight: 700;
}

.card {
    background-color:#121827;
    height: 100%;
    padding: 0;
    font-family: $sariko-font-family-secondary;
    overflow-x: hidden;
    border-radius: 0.75rem;
    cursor: pointer;
}


.food-info {
    padding: 10px;
}

.price-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 4px;
}

.food-name {
    font-size: 12px;
    font-weight: 700;
}

.seller-name {
    font-size: 10px;
    color: var(--text-muted, #8892a4);
    margin-top: 2px;
}

.food-price {
    font-weight: 600;
    color: var(--text-active);
}

</style>
