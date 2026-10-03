import { apiClient } from "@/lib/axiosPolicy.js"

export const apiAddress = {

    search: async (q) => {
        const response = await apiClient.get('/v1/address/search', { params: { q } })
        return response.data
    },

    getDetail: async (placeId) => {
        const response = await apiClient.get('/v1/address/detail', { params: { place_id: placeId } })
        return response.data
    },

    reverse: async (lat, lon) => {
        const response = await apiClient.get('/v1/address/reverse', { params: { lat, lon } })
        return response.data
    },

}

export default apiAddress
