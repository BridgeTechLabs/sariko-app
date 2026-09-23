import { apiClient } from "@/lib/axiosPolicy.js"

export const apiSellerDashboard = {

    getSellerInfo: async () => {
        const response = await apiClient.get('/v1/sellers/me')
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

}

export default apiSellerDashboard
