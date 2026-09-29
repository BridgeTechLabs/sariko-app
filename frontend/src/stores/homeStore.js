import { defineStore } from "pinia";
import { categories } from "@/stores/data.js";
import { apiSellers } from "@/apis/sellers/apiSellers.js";
import { foodPriceDisplay, hasVariants } from '@/utils/priceDisplay'

export const useHomeStore = defineStore('homeStore', {
    state: () => {
        return {
            searchQuery: '',
            categories: categories,
            selectedCategory: null,
            featuredDishes: [],
        }
    },

    actions: {
        async fetchFeaturedDishes() {
            try {
                const res = await apiSellers.getFeaturedDishes()
                if (res.data?.success) {
                    this.featuredDishes = res.data.featured_dishes.map(d => ({
                        id: d.id,
                        name: d.name,
                        price: foodPriceDisplay(d),
                        hasVariants: hasVariants(d),
                        imgSrc: d.image_url,
                        sellerId: d.seller_profiles?.id,
                        sellerSlug: d.seller_profiles?.slug,
                        sellerName: d.seller_profiles?.store_name,
                    }))
                }
            } catch (e) {
                console.error(`homeStore - fetchFeaturedDishes - ${e}`)
            }
        }
    }
})
