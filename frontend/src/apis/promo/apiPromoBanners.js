import { apiClient } from "@/lib/axiosPolicy.js"

// Public home banners (top + footer), set on the admin app. _silent: a failure shows no carousel, never a toast.
export const apiPromoBanners = {

    list: async () => {
        const res = await apiClient.get('/v1/promo-banners', { _silent: true })
        return res.data
    },
}
