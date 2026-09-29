<script>
import { Store } from 'lucide-vue-next'
import { mapActions, mapState } from 'pinia';
import { useCartStore } from '@/stores/cart/cartStore.js';
import ItemCard from '@/components/order-cart/ItemCard.vue';

export default {

    components: {
        Store,
        ItemCard
    },

    setup() {
        
    },

    data() {
        return {
            isExpanded: true 
        }
    },

    computed: {
        ...mapState(useCartStore, [
            "cartItems"
        ])
    },

    mounted() {
        if (!this.cartItems.length) {
            const cartStore = useCartStore()
            cartStore.getCurrentCart()
        }
    }
}

</script>

<template>
    <div class="background">
        <div class="container">

            <div class="header">
                <div class="seller-store">
                    <Store class="icon" />
                    {{ cartItems[0]?.sellerStore }}
                    <span class="item-count">{{ cartItems.length }}</span>
                </div>
                <div v-on:click="isExpanded=!isExpanded">
                    <q-icon :name="isExpanded ? 'expand_less' : 'expand_more'" />
                </div>
            </div>
            <div v-if="isExpanded" class="items">
                <ItemCard  v-for="item in cartItems"
                :key="item.rowKey"
                :item-id="item.id"
                :item-name="item.name"
                :item-price="item.price"
                :item-price-text="item.priceText"
                :item-category="item.category"
                :item-img-src="item.imgSrc || '/images/default-food-image.webp'"
                :item-quantity="item.quantity"
                :item-variant-id="item.variantId"
                :item-variant-name="item.variantName"
                :seller-store="item.sellerStore"
                :seller-slug-name="item.sellerSlugName"
                />
            </div>
        </div>
    </div>
</template>

<style lang="scss" scoped>
.container {
    padding: 0px 10px;
    border-radius: .75rem;
}

.cart-items-scroll-area {
    height: calc(100vh - var(--breadcrumbs-height) - var(--total-amount-height) - var(--delivery-adress-height) - 40px);
    height: calc(100dvh - var(--breadcrumbs-height) - var(--total-amount-height) - var(--delivery-adress-height) - 40px);
    white-space: nowrap;
}

.header {
    display: flex;
    // background-color: var(--bg-surface);
    border: 1px solid var(--border-color);
    align-items: center;
    justify-content: space-between;
    padding: 15px 15px 15px 10px;
    border-top-left-radius: 1rem;
    border-top-right-radius: 1rem;
    background: rgba(255, 255, 255, 0.05);
}   

.seller-store {
    display: flex;
    align-items: center;
    font-size: 14px;
    color: var(--text-muted);
}

.icon {
    margin-right: 5px;
}

.item-count {
    margin-left: 8px;
    font-size: 11px;
    font-weight: 700;
    background-color: $accent;
    color: var(--bg-main);
    padding: 1px 8px;
    border-radius: 1rem;
}

.items {
    border: 1px solid var(--border-color);
    border-top: 0px;
    // background-color: var(--bg-surface);
    border-bottom-left-radius: 1rem;
    border-bottom-right-radius: 1rem;
    background: rgba(255, 255, 255, 0.05);
}
</style>