import { apiClient } from "@/lib/axiosPolicy.js"

export const apiReviews = {

    createReview: async (orderId, overallRating, overallComment = null, items = []) => {
        try {
            const payload = {
                order_id: orderId,
                overall_rating: overallRating,
                overall_comment: overallComment,
                items,
            }
            const response = await apiClient.post('/v1/reviews', payload)
            return response
        } catch (error) {
            // Surface the backend's own message (409 "Order already reviewed",
            // 400 "Only completed orders…") so the caller can react to the reason.
            const err = new Error(error.response?.data?.detail || 'Failed to createReview')
            err.status = error.response?.status
            throw err
        }
    },

    getOrderReview: async (orderId) => {
        try {
            const response = await apiClient.get(`/v1/reviews/orders/${orderId}`)
            return response
        } catch (error) {
            throw new Error(error.response?.data?.detail || 'Failed to getOrderReview')
        }
    },

    getFoodItemReviews: async (foodItemId, { limit = 20, offset = 0 } = {}) => {
        try {
            const response = await apiClient.get(`/v1/reviews/food/${foodItemId}`, {
                params: { limit, offset }
            })
            return response
        } catch (error) {
            throw new Error(error.response?.data?.detail || 'Failed to getFoodItemReviews')
        }
    },
}

export default apiReviews
