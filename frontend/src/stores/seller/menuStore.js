import { defineStore } from 'pinia'
import { useDashboardStore } from '@/stores/seller/dashboardStore'
import apiSellerMenu from '@/apis/sellers/apiSellerMenu'
import { fileToBase64 } from '@/utils/fileToBase64'

export const useMenuStore = defineStore('menuStore', {
    state() {
        return {
            categories: [],   // [{ id, name, sort_order, is_active, food_items: [...] }]
            isLoading: false,
            sellerId: null,
        }
    },

    getters: {
        allItems(state) {
            return state.categories.flatMap(c => c.food_items || [])
        },
    },

    actions: {
        async fetchMenu() {
            this.isLoading = true
            try {
                const dashStore = useDashboardStore()
                if (!dashStore.sellerId) await dashStore.fetchSellerInfo()
                this.sellerId = dashStore.sellerId

                const res = await apiSellerMenu.getMenu()
                this.categories = res.menu || []
            } catch (e) {
                console.error('menuStore - fetchMenu -', e)
            } finally {
                this.isLoading = false
            }
        },

        // ── Categories ──────────────────────────────────────────────────────

        async createCategory(name) {
            const maxOrder = this.categories.reduce((m, c) => Math.max(m, c.sort_order || 0), 0)
            const res = await apiSellerMenu.createCategory(name, maxOrder + 1)
            this.categories.push({ ...res.category, food_items: [] })
            return res.category
        },

        async updateCategory(catId, fields) {
            const res = await apiSellerMenu.updateCategory(catId, fields)
            const idx = this.categories.findIndex(c => c.id === catId)
            if (idx !== -1) Object.assign(this.categories[idx], res.category)
        },

        async deleteCategory(catId) {
            await apiSellerMenu.deleteCategory(catId)
            this.categories = this.categories.filter(c => c.id !== catId)
        },

        // ── Food Items ───────────────────────────────────────────────────────

        async createItem(fields) {
            const res = await apiSellerMenu.createItem(fields)
            const item = res.item
            const cat = this.categories.find(c => c.id === item.category_id)
            if (cat) {
                if (!cat.food_items) cat.food_items = []
                cat.food_items.push(item)
            }
            return item
        },

        async updateItem(itemId, fields) {
            const res = await apiSellerMenu.updateItem(itemId, fields)
            const updated = res.item
            for (const cat of this.categories) {
                const idx = (cat.food_items || []).findIndex(i => i.id === itemId)
                if (idx !== -1) {
                    // Handle category change
                    if (updated.category_id !== cat.id) {
                        cat.food_items.splice(idx, 1)
                        const newCat = this.categories.find(c => c.id === updated.category_id)
                        if (newCat) {
                            if (!newCat.food_items) newCat.food_items = []
                            newCat.food_items.push(updated)
                        }
                    } else {
                        Object.assign(cat.food_items[idx], updated)
                    }
                    break
                }
            }
            return updated
        },

        async deleteItem(itemId) {
            await apiSellerMenu.deleteItem(itemId)
            for (const cat of this.categories) {
                const idx = (cat.food_items || []).findIndex(i => i.id === itemId)
                if (idx !== -1) { cat.food_items.splice(idx, 1); break }
            }
        },

        async toggleAvailable(itemId, isAvailable) {
            return this.updateItem(itemId, { is_available: isAvailable })
        },

        // ── Price variants ───────────────────────────────────────────────────
        // The modal buffers edits and calls syncVariants once, on save.
        // `desired` rows without an id are new; ids missing from it are deleted.

        async syncVariants(itemId, desired) {
            const item = this.allItems.find(i => i.id === itemId)
            const current = item?.food_item_variants || []

            const keptIds = desired.filter(v => v.id).map(v => v.id)
            for (const old of current) {
                if (!keptIds.includes(old.id)) await apiSellerMenu.deleteVariant(old.id)
            }

            const saved = []
            for (const [i, v] of desired.entries()) {
                const fields = {
                    name: v.name.trim(),
                    price: Number(v.price),
                    sort_order: i,
                    is_available: v.is_available !== false,
                }
                const res = v.id
                    ? await apiSellerMenu.updateVariant(v.id, fields)
                    : await apiSellerMenu.createVariant(itemId, fields)
                saved.push(res.variant)
            }

            if (item) item.food_item_variants = saved
            return saved
        },

        // ── Image upload (via backend, service role) ─────────────────────────

        async uploadImage(itemId, file) {
            const imageBase64 = await fileToBase64(file)
            const res = await apiSellerMenu.uploadItemImage(itemId, imageBase64, file.type)
            return res.image_url
        },
    },
})
