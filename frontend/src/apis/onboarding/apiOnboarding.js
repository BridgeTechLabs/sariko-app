import { apiClient } from "@/lib/axiosPolicy.js"

// Public seller application (/join). _silent: the form shows errors inline instead of toasts.
export const apiOnboarding = {

    // Limits (admin_settings + plan limits). The form never hardcodes them.
    getSettings: async () => {
        const res = await apiClient.get('/v1/onboarding/settings', { _silent: true })
        return res.data
    },

    createApplication: async (payload) => {
        const res = await apiClient.post('/v1/onboarding/applications', payload, { _silent: true })
        return res.data
    },

    uploadFile: async (applicationId, uploadToken, fields) => {
        const res = await apiClient.post(`/v1/onboarding/applications/${applicationId}/files`, fields, {
            _silent: true,
            timeout: 120000, // 5 MB over 4G
            headers: { 'X-Upload-Token': uploadToken },
        })
        return res.data
    },

    submitApplication: async (applicationId, uploadToken) => {
        const res = await apiClient.post(`/v1/onboarding/applications/${applicationId}/submit`, {}, {
            _silent: true,
            headers: { 'X-Upload-Token': uploadToken },
        })
        return res.data
    },
}

export default apiOnboarding
