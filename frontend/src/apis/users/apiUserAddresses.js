import { apiClient } from "@/lib/axiosPolicy.js"

export const apiUserAddresses = {

    list: async () => {
        const response = await apiClient.get('/v1/user_addresses')
        return response.data
    },

    create: async (data) => {
        const response = await apiClient.post('/v1/user_addresses', data)
        return response.data
    },

    update: async (id, data) => {
        const response = await apiClient.patch(`/v1/user_addresses/${id}`, data)
        return response.data
    },

}

export default apiUserAddresses
