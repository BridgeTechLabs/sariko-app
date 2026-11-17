import { apiClient } from "@/lib/axiosPolicy.js"

export const apiSellerMenu = {

    getMenu: async () => {
        const res = await apiClient.get('/v1/sellers/me/menu')
        return res.data
    },

    // Categories
    createCategory: async (name, sortOrder = 0) => {
        const res = await apiClient.post('/v1/sellers/me/menu/categories', { name, sort_order: sortOrder })
        return res.data
    },

    updateCategory: async (catId, fields) => {
        const res = await apiClient.patch(`/v1/sellers/me/menu/categories/${catId}`, fields)
        return res.data
    },

    deleteCategory: async (catId) => {
        const res = await apiClient.delete(`/v1/sellers/me/menu/categories/${catId}`)
        return res.data
    },

    // Food items
    createItem: async (fields) => {
        const res = await apiClient.post('/v1/sellers/me/menu/items', fields)
        return res.data
    },

    updateItem: async (itemId, fields) => {
        const res = await apiClient.patch(`/v1/sellers/me/menu/items/${itemId}`, fields)
        return res.data
    },

    deleteItem: async (itemId) => {
        const res = await apiClient.delete(`/v1/sellers/me/menu/items/${itemId}`)
        return res.data
    },

    // Price variants (one required, single-select level per dish)
    createVariant: async (itemId, fields) => {
        const res = await apiClient.post(`/v1/sellers/me/menu/items/${itemId}/variants`, fields)
        return res.data
    },

    updateVariant: async (variantId, fields) => {
        const res = await apiClient.patch(`/v1/sellers/me/menu/variants/${variantId}`, fields)
        return res.data
    },

    deleteVariant: async (variantId) => {
        const res = await apiClient.delete(`/v1/sellers/me/menu/variants/${variantId}`)
        return res.data
    },

    // Option groups (seller-menu đợt 3): made from a dish, shared by the dishes they are put on
    createOptionGroup: async (itemId, body) => {
        const res = await apiClient.post(`/v1/sellers/me/menu/items/${itemId}/option-groups`, body)
        return res.data
    },

    updateOptionGroup: async (groupId, body) => {
        const res = await apiClient.put(`/v1/sellers/me/menu/option-groups/${groupId}`, body)
        return res.data
    },

    deleteOptionGroup: async (groupId) => {
        const res = await apiClient.delete(`/v1/sellers/me/menu/option-groups/${groupId}`)
        return res.data
    },

    attachOptionGroup: async (itemId, groupId) => {
        const res = await apiClient.post(`/v1/sellers/me/menu/items/${itemId}/option-groups/${groupId}`)
        return res.data
    },

    detachOptionGroup: async (itemId, groupId) => {
        const res = await apiClient.delete(`/v1/sellers/me/menu/items/${itemId}/option-groups/${groupId}`)
        return res.data
    },

    orderOptionGroups: async (itemId, groupIds) => {
        const res = await apiClient.put(`/v1/sellers/me/menu/items/${itemId}/option-groups`, { group_ids: groupIds })
        return res.data
    },

    uploadItemImage: async (itemId, imageBase64, contentType) => {
        const res = await apiClient.post(`/v1/sellers/me/menu/items/${itemId}/image`, { image_base64: imageBase64, content_type: contentType })
        return res.data
    },

}

export default apiSellerMenu
