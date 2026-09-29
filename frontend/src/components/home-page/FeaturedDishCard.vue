<script>
import { useCartStore } from '@/stores/cart/cartStore';
import { useAuthStore } from '@/stores/auth/authStore';

export default {
    name: 'FeaturedDishCard',
    props: {
        hasVariants: {
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
            this.$router.push(`/food/${this.sellerSlug}/${this.itemId}`)
        },

        async handleAddToCart(e) {
            e.stopPropagation()
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
            await cartStore.addItem(this.sellerId, this.itemId, this.sellerName)
            this.loading = false
            if (!cartStore.isShowModalCartConflict) {
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
            />
        </div>

        <div class="food-info">
            <div class="food-name">{{ name }}</div>
            <div class="seller-name">{{ sellerName }}</div>
            <div class="price-row">
                <div class="food-price">₫{{ price }}</div>
                <q-btn flat dense no-caps :loading="loading" @click="handleAddToCart">
                    <q-icon name="fa-solid fa-circle-plus" style="color: #f5A623" />
                    <template #loading>
                        <q-spinner-dots color="orange" size="16px" />
                    </template>
                </q-btn>
            </div>
        </div>
    </div>
</template>

<style lang="scss" scoped>

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
