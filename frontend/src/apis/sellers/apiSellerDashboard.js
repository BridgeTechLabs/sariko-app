import { apiClient } from "@/lib/axiosPolicy.js"

export const apiSellerDashboard = {

    getSellerInfo: async () => {
        const response = await apiClient.get('/v1/sellers/me')
        return response.data
    },

    setStoreOpen: async (isOpen) => {
        const response = await apiClient.patch('/v1/sellers/me/open', { is_open: isOpen })
        return response.data
    },

    // "HH:MM" strings, or both null for open all day
    setStoreHours: async (openingTime, closingTime) => {
        const response = await apiClient.patch('/v1/sellers/me/hours', { opening_time: openingTime, closing_time: closingTime })
        return response.data
    },

    getOrders: async () => {
        const response = await apiClient.get('/v1/sellers/me/orders')
        return response.data
    },

    getOrderDetail: async (orderId) => {
        const response = await apiClient.get(`/v1/sellers/me/orders/${orderId}`)
        return response.data
    },

    updateOrderStatus: async (orderId, newStatus, cancellationReason = null) => {
        const payload = { status: newStatus }
        if (cancellationReason) payload.cancellation_reason = cancellationReason
        const response = await apiClient.patch(`/v1/sellers/me/orders/${orderId}/status`, payload)
        return response.data
    },

    getReviews: async (limit, offset) => {
        const response = await apiClient.get('/v1/sellers/me/reviews', { params: { limit, offset } })
        return response.data
    },

}

export default apiSellerDashboard
