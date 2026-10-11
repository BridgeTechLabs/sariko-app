import { apiClient } from "@/lib/axiosPolicy.js"

export const apiUsers = {

    getProfile: async () => {
        const response = await apiClient.get('/v1/users/info/me')
        return response.data
    },

    updateProfile: async (data) => {
        const response = await apiClient.patch('/v1/users/me/profile', data)
        return response.data
    },

    getDefaultAddress: async () => {
        const response = await apiClient.get('/v1/users/me/address')
        return response.data
    },

    uploadAvatar: async (imageBase64, contentType) => {
        const response = await apiClient.post('/v1/users/me/avatar', { image_base64: imageBase64, content_type: contentType })
        return response.data
    },

    createPushSubscription: async (subscription) => {
        const response = await apiClient.post('/v1/users/me/push-subscriptions', subscription)
        return response.data
    },

}

export default apiUsers
