import { defineStore } from 'pinia'
import apiProfileCompletion from '@/apis/sellers/apiProfileCompletion'
import { fileToBase64 } from '@/utils/fileToBase64'

// What the seller still has to fill in (GET /sellers/me/profile-completion). The backend
// decides "missing"; the banner on Today, the dot on Me and the form all read it from here.
export const useProfileCompletionStore = defineStore('profileCompletion', {
    state: () => ({
        data: null,             // { complete, missing, agreement_version_current, limits, prefill, id_document_files }
        loading: false,
        bannerCollapsed: true,  // starts collapsed (title row only); comes back collapsed on every reload while something is missing
    }),

    getters: {
        missing: (state) => state.data?.missing || [],
        complete: (state) => state.data?.complete === true,
    },

    actions: {
        async fetch() {
            this.loading = true
            try {
                this.data = await apiProfileCompletion.get()
            } catch (e) {
                console.error('profile completion:', e)
            } finally {
                this.loading = false
            }
        },

        // Throws the API error ({ code, ... } in response.data.detail) for the form to show.
        async save(payload) {
            this.data = await apiProfileCompletion.save(payload)
            return this.data
        },

        async uploadIdDocument(file) {
            this.data = await apiProfileCompletion.uploadIdDocument(await fileToBase64(file))
            return this.data
        },
    },
})
