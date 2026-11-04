import { apiClient } from "@/lib/axiosPolicy.js"

// Existing seller completes their profile (identity, tax, bank, contact, agreement).
// _silent: the form shows errors next to the fields instead of a toast.
export const apiProfileCompletion = {

    get: async () => {
        const res = await apiClient.get('/v1/sellers/me/profile-completion', { _silent: true })
        return res.data
    },

    save: async (payload) => {
        const res = await apiClient.post('/v1/sellers/me/profile-completion', payload, { _silent: true })
        return res.data
    },

    uploadIdDocument: async (fileBase64) => {
        const res = await apiClient.post('/v1/sellers/me/profile-completion/files',
            { kind: 'id_document', file_base64: fileBase64 },
            { _silent: true, timeout: 120000 })  // 5 MB over 4G
        return res.data
    },
}

export default apiProfileCompletion
