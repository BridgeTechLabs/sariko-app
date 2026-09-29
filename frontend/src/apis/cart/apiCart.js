import { apiClient } from "@/lib/axiosPolicy.js"

export const apiCarts = {

    addItem: async(sellerId, foodItemId, quantity = 1, variantId = null) => {
        try {
            const payload = {
                "seller_id": sellerId,
                "food_item_id": foodItemId,
                "quantity": quantity,
                "variant_id": variantId
            }
            const response = await apiClient.post('/v1/cart/add', payload, { _silent: true })
            return response
        } catch (error) {
            const detail = error.response?.data?.detail
            if (detail?.message === 'Cart contains items from another seller') {
                const err = new Error('another seller')
                err.currentSellerName = detail.current_seller_name
                throw err
            }
            throw new Error(detail || 'Failed to addItem')
        }
    },

    getCart: async() => {
        try {
            const response = await apiClient.get('/v1/cart')
            return response
        } catch (error) {
            throw new Error(error.response?.data?.detail || 'Failed to getCart')
        }
    },

    updateQuantity: async(foodItemId, newQuantity, variantId = null) => {
        try {
            const payload = {
                "food_item_id": foodItemId,
                "quantity": newQuantity,
                "variant_id": variantId
            }
            const response = await apiClient.patch('/v1/cart/update', payload)
            return response
        } catch (error) {
            throw new Error(error.response?.data?.detail || 'Failed to updateQuantity')
        }
    },

    clearCart: async() => {
        try {
            const response = await apiClient.delete('/v1/cart/clear')
            return response
        } catch (error) {
            throw new Error(error.response?.data?.detail || 'Failed to clearCart')
        }
    },

    removeItem: async(foodItemId, variantId = null) => {
        try {
            const params = variantId ? { variant_id: variantId } : {}
            const response = await apiClient.delete(`/v1/cart/remove/${foodItemId}`, { params })
            return response
        } catch (error) {
            throw new Error(error.response?.data?.detail || 'Failed to removeItem')
        }
    }

}

export default apiCarts;