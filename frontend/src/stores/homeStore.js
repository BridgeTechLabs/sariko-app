import { defineStore } from "pinia";
import { categories } from "@/stores/data.js";
import { apiSellers } from "@/apis/sellers/apiSellers.js";
import { apiPromoBanners } from "@/apis/promo/apiPromoBanners.js";
import { foodPriceDisplay, picksOnDetail } from '@/utils/priceDisplay'

export const useHomeStore = defineStore('homeStore', {
    state: () => {
        return {
            searchQuery: '',
            categories: categories,
            selectedCategory: null,
            featuredDishes: [],
            promoBanners: null,   // top of the page; null = loading; [] = none or failed (no carousel)
            footerBanners: null,  // just above the footer, same rules
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
                        hasVariants: picksOnDetail(d),
                        soldOut: !!d.sold_out,
                        imgSrc: d.image_url,
                        sellerId: d.seller_profiles?.id,
                        sellerSlug: d.seller_profiles?.slug,
                        sellerName: d.seller_profiles?.store_name,
                    }))
                }
            } catch (e) {
                console.error(`homeStore - fetchFeaturedDishes - ${e}`)
            }
        },

        async fetchPromoBanners() {
            try {
                const res = await apiPromoBanners.list()
                this.promoBanners = res.banners || []
                this.footerBanners = res.footer_banners || []
            } catch (e) {
                this.promoBanners = []
                this.footerBanners = []
            }
        }
    }
})
