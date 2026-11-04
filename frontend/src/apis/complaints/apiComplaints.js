import { apiClient } from "@/lib/axiosPolicy.js"

// Errors keep the backend's {code, message, ...} detail so the screen can name the reason.
function apiError(error, fallback) {
    const detail = error.response?.data?.detail
    const err = new Error(detail?.message || fallback)
    err.status = error.response?.status
    err.code = detail?.code
    err.params = detail || {}
    return err
}

export const apiComplaints = {

    getConfig: async () => {
        try {
            return (await apiClient.get('/v1/complaints/config')).data
        } catch (error) {
            throw apiError(error, 'Failed to getConfig')
        }
    },

    create: async (orderId, category, description) => {
        try {
            const payload = { order_id: orderId, category, description }
            return (await apiClient.post('/v1/complaints', payload)).data
        } catch (error) {
            throw apiError(error, 'Failed to create complaint')
        }
    },

    uploadImage: async (complaintId, imageBase64) => {
        try {
            return (await apiClient.post(`/v1/complaints/${complaintId}/images`, { image_base64: imageBase64 })).data
        } catch (error) {
            throw apiError(error, 'Failed to upload photo')
        }
    },

    getMine: async () => {
        try {
            return (await apiClient.get('/v1/complaints/mine')).data
        } catch (error) {
            throw apiError(error, 'Failed to getMine')
        }
    },

    getDetail: async (complaintId) => {
        try {
            return (await apiClient.get(`/v1/complaints/${complaintId}`)).data
        } catch (error) {
            throw apiError(error, 'Failed to getDetail')
        }
    },
}

export default apiComplaints
