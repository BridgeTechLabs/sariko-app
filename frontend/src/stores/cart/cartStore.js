import { defineStore } from "pinia";
import apiCarts from "@/apis/cart/apiCart";

export const useCartStore = defineStore("cartStore", {
    state() {
        return {
            cart: null,
            cartItems: [],

            // modal conflict store
            firstSeller: null,
            secondSeller: null,
            isShowModalCartConflict: false,
            pendingSellerId: null,
            pendingFoodItemId: null,
            pendingVariantId: null,
            pendingSellerName: null,

            // note
            note: ''
        }
    },

    getters: {
        subtotal(state) {
            return state.cartItems.reduce((sum, item) => sum + item.price * item.quantity, 0)
        },
        subtotalText() {
            return new Intl.NumberFormat('vi-VN').format(this.subtotal) + ' ₫'
        },
        itemCount(state) {
            return state.cartItems.reduce((sum, item) => sum + item.quantity, 0)
        },
        currentSellerSlug(state) {
            return state.cartItems[0]?.sellerSlugName || null
        },
        maxPreorderDay(state) {
            return Math.max(0, ...state.cartItems.map(i => i.preorder_day ?? 0))
        }
    },

    actions: {
        async getCurrentCart() {
            try {
                const res = await apiCarts.getCart()
                if ((res.data?.success) && (res.data?.cart)) {
                    this.cart = res.data.cart
                    this.cartItems = []

                    const _cartItems = this.cart.cart_items
                    for (let i=0; i<_cartItems.length; i++) {
                        const _variant = _cartItems[i]?.food_item_variants || null
                        this.cartItems.push({
                            "id": _cartItems[i]?.food_items?.id,
                            // Same dish at two levels = two rows sharing one id, so
                            // every local lookup and :key must use rowKey, not id.
                            "rowKey": `${_cartItems[i]?.food_items?.id}::${_variant?.id || ''}`,
                            "variantId": _variant?.id || null,
                            "variantName": _variant?.name || null,
                            "name": _cartItems[i]?.food_items?.name,
                            "price": _variant ? _variant.price : _cartItems[i]?.food_items?.price,
                            "priceText": _variant ? _variant.price_text : _cartItems[i]?.food_items?.price_text,
                            "imgSrc": _cartItems[i]?.food_items?.image_url,
                            "category":  _cartItems[i]?.food_items?.menu_categories?.name,
                            "quantity": _cartItems[i]?.quantity,
                            "sellerStore": this.cart?.seller_profiles?.store_name,
                            "sellerSlugName": this.cart?.seller_profiles?.slug,
                            "preorder_day": _cartItems[i]?.food_items?.preorder_day ?? 0,
                        })
                    }
                }
            } catch (e) {
                console.error(`cartStore - getCurrentCart - ${e}`);
            }
        },

        async addItem(sellerId, foodItemId, newSellerName, quantity = 1, variantId = null) {
            try {
                await apiCarts.addItem(sellerId, foodItemId, quantity, variantId)
                await this.refreshCart()
            } catch (e) {
                if (e.message === 'another seller') {
                    this.pendingSellerId = sellerId
                    this.pendingFoodItemId = foodItemId
                    this.pendingVariantId = variantId
                    this.pendingSellerName = newSellerName
                    this.showConflictModal(e.currentSellerName || '', newSellerName || '')
                } else {
                    console.error(`cartStore - addItem - ${e}`)
                }
            }
        },

        async clearCartAndAddItem() {
            try {
                await apiCarts.clearCart()
                this.cart = null
                this.cartItems = []
                this.isShowModalCartConflict = false

                if (this.pendingSellerId && this.pendingFoodItemId) {
                    await apiCarts.addItem(this.pendingSellerId, this.pendingFoodItemId, 1, this.pendingVariantId)
                    await this.refreshCart()
                }

                this.pendingSellerId = null
                this.pendingFoodItemId = null
                this.pendingVariantId = null
                this.pendingSellerName = null
            } catch (e) {
                console.error(`cartStore - clearCartAndAddItem - ${e}`)
            }
        },

        async refreshCart() {
            this.cart = null
            this.cartItems = []
            await this.getCurrentCart()
        },

        async updateQuantity(foodItemId, newQuantity, variantId = null) {
            try {
                await apiCarts.updateQuantity(foodItemId, newQuantity, variantId)
                const rowKey = `${foodItemId}::${variantId || ''}`
                const item = this.cartItems.find(i => i.rowKey === rowKey)
                if (item) item.quantity = newQuantity
            } catch (e) {
                console.error(`cartStore - updateQuantity - ${e}`);
            }
        },

        async removeItem(foodItemId, variantId = null) {
            try {
                await apiCarts.removeItem(foodItemId, variantId)
                const rowKey = `${foodItemId}::${variantId || ''}`
                this.cartItems = this.cartItems.filter(i => i.rowKey !== rowKey)
            } catch (e) {
                console.error(`cartStore - removeItem - ${e}`);
            }
        },

        showConflictModal(firstSeller, secondSeller) {
            this.firstSeller = firstSeller
            this.secondSeller = secondSeller
            this.isShowModalCartConflict = true
        }
    }
})