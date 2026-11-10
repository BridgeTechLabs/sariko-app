import { apiClient } from "@/lib/axiosPolicy.js"

export const apiDeliveries = {

    getQuotation: async (sellerId, deliveryLat, deliveryLon, deliveryAddress) => {
        const payload = {
            seller_id: sellerId,
            delivery_lat: deliveryLat,
            delivery_lon: deliveryLon,
            delivery_address: deliveryAddress,
        }
        const response = await apiClient.post('/v1/deliveries/quotation', payload)
        return response.data
    },

    getDeliveryStatus: async (orderId) => {
        const response = await apiClient.get(`/v1/deliveries/${orderId}/status`)
        return response.data
    },

    getSellerDeliveryStatus: async (orderId) => {
        const response = await apiClient.get(`/v1/deliveries/${orderId}/seller-status`)
        return response.data
    },

    rebookDelivery: async (orderId) => {
        const response = await apiClient.post(`/v1/deliveries/${orderId}/rebook`)
        return response.data
    },

}

export default apiDeliveries
