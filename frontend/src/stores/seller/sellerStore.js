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
            selectedOptionIds: [],
        }
    },

    getters: {
        // The dish page's option groups (seller-menu đợt 3); the server prices and checks them again
        foodGroups(state) {
            return state.currentFood?.option_groups || []
        },
        optionsExtra() {
            return this.foodGroups.flatMap(g => g.menu_options)
                .filter(o => this.selectedOptionIds.includes(o.id))
                .reduce((sum, o) => sum + Number(o.extra_price), 0)
        },
        // First required group with nothing picked: the add button waits for it
        missingGroup() {
            return this.foodGroups.find(g => g.is_required && !g.menu_options.some(o => this.selectedOptionIds.includes(o.id))) || null
        },

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
            this.selectedOptionIds = []

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
        },

        // Choose 1 replaces the group's pick (a required one can't be emptied); Up to N stops at N
        toggleOption(group, optionId) {
            const inGroup = new Set(group.menu_options.map(o => o.id))
            const picked = this.selectedOptionIds.filter(id => inGroup.has(id))
            if (picked.includes(optionId)) {
                if (!(group.is_required && group.max_select === 1)) this.selectedOptionIds = this.selectedOptionIds.filter(id => id !== optionId)
            } else if (group.max_select === 1) {
                this.selectedOptionIds = [...this.selectedOptionIds.filter(id => !inGroup.has(id)), optionId]
            } else if (picked.length < group.max_select) {
                this.selectedOptionIds = [...this.selectedOptionIds, optionId]
            }
        }
    }
})