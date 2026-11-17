import { defineStore } from "pinia";
import apiCarts from "@/apis/cart/apiCart";
import { Notify } from "quasar";
import { i18n } from "@/plugins/i18n";
import { apiErrorMessage } from "@/lib/axiosPolicy.js";
import { stockLeft, minShortByFood } from "@/utils/portions";

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
            pendingOptionIds: [],
            pendingQuantity: 1,
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
        // Same wording as the backend's unavailable_names: dish, or dish (level)
        unavailableNames(state) {
            return state.cartItems.filter(i => i.unavailable).map(i => i.variantName ? `${i.name} (${i.variantName})` : i.name)
        },
        // Rows whose options no longer fit the dish (the server's check, GET /cart): fixed before ordering
        hasOptionProblem(state) {
            return state.cartItems.some(i => i.problem)
        },
        // Dishes below their minimum per order (utils/portions.js): the order is refused (400) until fixed
        minShortByFood(state) {
            return minShortByFood(state.cartItems)
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
                            // One dish can be several rows (other level or options): the row's own id
                            // is the key and what +/- and remove send.
                            "rowKey": _cartItems[i]?.id,
                            "variantId": _variant?.id || null,
                            "variantName": _variant?.name || null,
                            "name": _cartItems[i]?.food_items?.name,
                            // Priced by the server (level or dish + options): what the order will charge
                            "price": _cartItems[i]?.unit_price,
                            "options": _cartItems[i]?.options || [],
                            "problem": _cartItems[i]?.problem || null,
                            "imgSrc": _cartItems[i]?.food_items?.image_url,
                            "category":  _cartItems[i]?.food_items?.menu_categories?.name,
                            "quantity": _cartItems[i]?.quantity,
                            "sellerStore": this.cart?.seller_profiles?.store_name,
                            "sellerSlugName": this.cart?.seller_profiles?.slug,
                            "preorder_day": _cartItems[i]?.food_items?.preorder_day ?? 0,
                            // The seller can switch a dish or level off after it went into the cart
                            // Stock left (null = no limit) and the dish's minimum per order
                            "portionsLeft": stockLeft(_cartItems[i]?.food_items),
                            "minQuantity": _cartItems[i]?.food_items?.min_quantity ?? 1,
                            "unavailable": _cartItems[i]?.food_items?.is_available === false || _variant?.is_available === false || _cartItems[i]?.food_items?.sold_out === true,
                        })
                    }
                }
            } catch (e) {
                console.error(`cartStore - getCurrentCart - ${e}`);
            }
        },

        async addItem(sellerId, foodItemId, newSellerName, quantity = 1, variantId = null, optionIds = []) {
            try {
                await apiCarts.addItem(sellerId, foodItemId, quantity, variantId, optionIds)
                await this.refreshCart()
                return true
            } catch (e) {
                if (e.message === 'another seller') {
                    this.pendingSellerId = sellerId
                    this.pendingFoodItemId = foodItemId
                    this.pendingVariantId = variantId
                    this.pendingOptionIds = optionIds
                    this.pendingQuantity = quantity
                    this.pendingSellerName = newSellerName
                    this.showConflictModal(e.currentSellerName || '', newSellerName || '')
                } else if (e.detail?.code) {   // portions_left, quantity_max, the option checks...: translated by code
                    Notify.create({ classes: 'quasar-notify-negative', message: apiErrorMessage({ detail: e.detail }), position: 'bottom', timeout: 3000 })
                } else if (e.message.includes('sold out')) {
                    Notify.create({ classes: 'quasar-notify-negative', message: i18n.global.t('cart_page.dish_sold_out'), position: 'bottom', timeout: 3000 })
                } else if (e.message.includes('store is closed')) {
                    Notify.create({ classes: 'quasar-notify-negative', message: i18n.global.t('cart_page.store_closed_same_day'), position: 'bottom', timeout: 3000 })
                } else {
                    console.error(`cartStore - addItem - ${e}`)
                }
                return false
            }
        },

        async clearCartAndAddItem() {
            try {
                await apiCarts.clearCart()
                this.cart = null
                this.cartItems = []
                this.isShowModalCartConflict = false

                if (this.pendingSellerId && this.pendingFoodItemId) {
                    await apiCarts.addItem(this.pendingSellerId, this.pendingFoodItemId, this.pendingQuantity, this.pendingVariantId, this.pendingOptionIds)
                    await this.refreshCart()
                }

                this.pendingSellerId = null
                this.pendingFoodItemId = null
                this.pendingVariantId = null
                this.pendingOptionIds = []
                this.pendingQuantity = 1
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

        async updateQuantity(rowKey, newQuantity) {
            try {
                await apiCarts.updateQuantity(rowKey, newQuantity)
                const item = this.cartItems.find(i => i.rowKey === rowKey)
                if (item) item.quantity = newQuantity
            } catch (e) {
                console.error(`cartStore - updateQuantity - ${e}`);
            }
        },

        async removeItem(rowKey) {
            try {
                await apiCarts.removeItem(rowKey)
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