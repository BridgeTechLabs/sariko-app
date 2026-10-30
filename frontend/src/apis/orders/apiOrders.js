import { apiClient } from "@/lib/axiosPolicy.js"

export const apiOrders = {

    createOrder: async(deliveryMethod, deliveryAddress, note, deliveryOpts = {}, deliveryAppointment = null) => {
        try {
            const payload = {
                "delivery_method": deliveryMethod,
                "delivery_address": deliveryAddress,
                "note": note
            }
            if (deliveryOpts.delivery_lat != null) payload.delivery_lat = deliveryOpts.delivery_lat
            if (deliveryOpts.delivery_lon != null) payload.delivery_lon = deliveryOpts.delivery_lon
            if (deliveryOpts.delivery_fee != null) payload.delivery_fee = deliveryOpts.delivery_fee
            if (deliveryOpts.quotation_id) payload.quotation_id = deliveryOpts.quotation_id
            for (const key of ['receiver_name', 'receiver_phone', 'delivery_note']) if (deliveryOpts[key]) payload[key] = deliveryOpts[key]
            if (deliveryAppointment) payload.delivery_appointment = deliveryAppointment
            const response = await apiClient.post('/v1/orders', payload)
            return response
        } catch (error) {
            // detail is an object on 409 "delivery fee changed": { message, delivery_fee, quotation_id }
            const detail = error.response?.data?.detail
            const err = new Error(detail?.message || detail || 'Failed to create order')
            err.detail = detail
            throw err
        }
    },

    getOrders: async() => {
        try {
            const response = await apiClient.get('/v1/orders')
            return response
        } catch (error) {
            throw new Error(error.response?.data?.detail || 'Failed to get orders')
        }
    },

    getOrderDetail: async(orderId) => {
        try {
            const response = await apiClient.get(`/v1/orders/${orderId}`)
            return response
        } catch (error) {
            throw new Error(error.response?.data?.detail || 'Failed to get order detail')
        }
    },

    cancelOrder: async(orderId) => {
        try {
            const response = await apiClient.patch(`/v1/orders/${orderId}/cancel`)
            return response
        } catch (error) {
            throw new Error(error.response?.data?.detail || 'Failed to cancel order')
        }
    }
}

export default apiOrders
