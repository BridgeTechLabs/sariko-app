import { defineStore } from 'pinia'
import { sellers, menus } from '@/stores/data.js'
import apiSellers from '@/apis/sellers/apiSellers'

export const useSellerStore = defineStore('sellerStore', {
    
    state: () => {
        return {
            sellers: sellers,
            seller: null,
            foundingSellers: [],

            // categories
            homeMenuCategories: [
                {id: 1, label: 'Lutong Bahay', icon: '🍲'},
                {id: 2, label: 'Silogs', icon: '🍳'},
                {id: 3, label: 'Noodles', icon: '🍜'},
                {id: 4, label: 'Desserts', icon: '🍮'},
                {id: 5, label: 'Frozen', icon: '❄️'},
                {id: 6, label: 'Others', icon: ''},
            ],
            selectedHomeMenuCategory: 'Lutong Bahay',

            // categories
            menuCategories: [
                {id: 1, label: 'Lutong Bahay', icon: '🍲'},
                {id: 2, label: 'Silogs', icon: '🍳'},
                {id: 3, label: 'Noodles', icon: '🍜'},
                {id: 4, label: 'Desserts', icon: '🍮'},
                {id: 5, label: 'Frozen', icon: '❄️'},
                {id: 6, label: 'Others', icon: ''},
            ],
            selectedCategoryMenu: 'Lutong Bahay',

            // menu
            menus: menus,
            totalItems: 0,

            // food detail
            currentFood: null,
            currentSeller: null,
            foodQuantity: 1,
            selectedVariantId: null,
        }
    },

    getters: {
        menu(state) {
            if (!state.selectedCategoryMenu || !state.menus.length) return []
            const category = state.menus.find(m => m.id === state.selectedCategoryMenu)
            return category?.food_items || []
        },

        filteredSellers() {
            let filtered = this.sellers;

            // Filter by category
            if (this.selectedCategory) {
                const categoryName = this.selectedCategoryName
                filtered = filtered.filter(s => s.category === categoryName)
            }

            // Filter by search query (match seller name, description, or contained menu items)
            if (this.searchQuery) {
                const query = this.searchQuery.toLowerCase();
                filtered = filtered.filter(seller =>
                    seller.name.toLowerCase().includes(query) ||
                    seller.description.toLowerCase().includes(query) ||
                    seller.menu.some(food => food.name.toLowerCase().includes(query))
                );
            }
            return filtered;
        },
    },

    actions: {
        
        async getFoundingSellers() {
            try {
                const res = await apiSellers.getFoundingSellers()
                if (res?.data) {
                    this.foundingSellers = res.data.founding_sellers
                }
            } catch (e) {
                console.error(`sellerStore - getFoundingSellers - ${e}`);
            }
        },

        async getSellerbySlugName(slugName) {
            try {
                const res = await apiSellers.getSellerbySlugName(slugName)
                if (res?.data) {
                    this.seller = res.data.seller
                }
            } catch (e) {
                console.error(`sellerStore - getSellerbySlugName - ${e}`);
            }
            
        },

        async getSellerFullMenu(slugName) {
            try {
                const res = await apiSellers.getSellerFullMenu(slugName)
                const menus = res?.data?.menus || []
                this.menus = menus
                this.menuCategories = menus.map(c => ({ id: c.id, name: c.name }))
                this.selectedCategoryMenu = menus.find(menu => menu.food_items?.length > 0)?.id || null

                this.totalItems = 0
                this.menus.forEach(menu => {
                    const itemLength = menu.food_items.length || 0
                    this.totalItems = this.totalItems + itemLength
                });

            } catch (e) {
                console.error(`sellerStore - getSellerFullMenu - ${e}`);
                this.menus = []
                this.menuCategories = []
                this.selectedCategoryMenu = null
            }
        },

        async loadFoodDetail(sellerSlug, foodId) {
            this.currentFood = null
            this.currentSeller = null
            this.foodQuantity = 1
            this.selectedVariantId = null

            // Load seller if not already loaded for this slug
            if (this.seller?.slug !== sellerSlug) {
                await this.getSellerbySlugName(sellerSlug)
                await this.getSellerFullMenu(sellerSlug)
            } else if (!this.menus.length || !this.menus[0]?.food_items) {
                await this.getSellerFullMenu(sellerSlug)
            }

            this.currentSeller = this.seller

            // Find food item across all menu categories
            for (const category of this.menus) {
                const found = category.food_items?.find(f => f.id === foodId)
                if (found) {
                    this.currentFood = found
                    // Preselect the first level on offer, so the buyer never faces
                    // a disabled button with no hint why.
                    const levels = (found.food_item_variants || []).filter(v => v.is_available !== false)
                    this.selectedVariantId = levels.length ? levels[0].id : null
                    break
                }
            }
        }
    }
})