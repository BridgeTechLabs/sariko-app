import axios from "axios"
import { apiClient } from "@/lib/axiosPolicy.js"

const baseURL = import.meta.env.VITE_API_BASE_URL || "/rest"

export const apiPayments = {

    createVnpayPayment: async(orderId) => {
        try {
            const response = await apiClient.post(`/v1/payments/vnpay/create/${orderId}`)
            return response
        } catch (error) {
            // 409 order_already_paid / payment_in_progress (T125): the caller reacts to the status;
            // axiosPolicy has already shown the translated message
            const err = new Error('Failed to create VNPay payment')
            err.status = error.response?.status
            err.code = error.response?.data?.detail?.code
            throw err
        }
    },

    checkVnpayReturn: async(queryParams) => {
        try {
            const response = await axios.get(`${baseURL}/v1/payments/vnpay/return?${queryParams}`)
            return response
        } catch (error) {
            throw new Error(error.response?.data?.detail || 'Failed to check payment status')
        }
    },

    pollPaymentStatus: async(orderId) => {
        try {
            const response = await apiClient.get(`/v1/payments/payment-status/${orderId}`)
            return response
        } catch (error) {
            throw new Error(error.response?.data?.detail || 'Failed to poll payment status')
        }
    }
}

export default apiPayments
