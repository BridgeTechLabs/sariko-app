import { defineStore } from 'pinia'
import { useDashboardStore } from '@/stores/seller/dashboardStore'
import apiSellerMenu from '@/apis/sellers/apiSellerMenu'
import { fileToBase64 } from '@/utils/fileToBase64'
import { copyGroupForDish } from '@/utils/optionGroups'

export const useMenuStore = defineStore('menuStore', {
    state() {
        return {
            categories: [],   // [{ id, name, sort_order, is_active, food_items: [...] }]
            optionGroups: [],   // the store's option groups, each with dish_ids (the dishes using it)
            optionLimits: {},   // admin_settings caps: menu_max_groups_per_dish, ..._options_per_group, ..._groups_per_store, menu_option_max_extra_price
            isLoading: false,
            loadError: false,   // last fetch failed: an error, not an empty menu
            sellerId: null,
        }
    },

    getters: {
        allItems(state) {
            return state.categories.flatMap(c => c.food_items || [])
        },
        // [names] of the dishes with these ids, in that order
        dishNames() {
            return ids => ids.map(id => this.allItems.find(i => i.id === id)?.name).filter(Boolean)
        },
    },

    actions: {
        async fetchMenu() {
            this.isLoading = true
            this.loadError = false
            try {
                const dashStore = useDashboardStore()
                if (!dashStore.sellerId) await dashStore.fetchSellerInfo()
                this.sellerId = dashStore.sellerId
                await this.reload()
            } catch (e) {
                console.error('menuStore - fetchMenu -', e)
                this.loadError = true
            } finally {
                this.isLoading = false
            }
        },

        // Reads the menu again without the loading state (the open forms stay mounted)
        async reload() {
            const res = await apiSellerMenu.getMenu()
            this.categories = res.menu || []
            this.optionGroups = res.option_groups || []
            this.optionLimits = res.option_limits || {}
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

        // Swap a category with its neighbour (step -1 up, +1 down) and save the new order.
        // sort_order may hold duplicates (all 0), so every category whose position
        // number changes is written, not just the two that swapped.
        async moveCategory(catId, step) {
            const from = this.categories.findIndex(c => c.id === catId)
            const to = from + step
            if (from === -1 || to < 0 || to >= this.categories.length) return
            const list = [...this.categories]
            ;[list[from], list[to]] = [list[to], list[from]]
            const changed = list.filter((c, i) => c.sort_order !== i + 1)
            this.categories = list.map((c, i) => Object.assign(c, { sort_order: i + 1 }))
            try {
                await Promise.all(changed.map(c => apiSellerMenu.updateCategory(c.id, { sort_order: c.sort_order })))
            } catch (e) {
                await this.fetchMenu()   // back to what the server has
                throw e
            }
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
                    // The PATCH answer has no option_groups / options_sold_out: the old object moves, updated
                    if (updated.category_id !== cat.id) {
                        const [moved] = cat.food_items.splice(idx, 1)
                        const newCat = this.categories.find(c => c.id === updated.category_id)
                        if (newCat) {
                            if (!newCat.food_items) newCat.food_items = []
                            newCat.food_items.push(Object.assign(moved, updated))
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
            for (const g of this.optionGroups) g.dish_ids = g.dish_ids.filter(id => id !== itemId)
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

        // ── Option groups (seller-menu đợt 3) ───────────────────────────────
        // A group shows on every dish using it, so each change reads the menu again (also after a failure).

        async saveOptionGroup(groupId, body, dishId) {
            try {
                if (groupId) await apiSellerMenu.updateOptionGroup(groupId, body)
                else await apiSellerMenu.createOptionGroup(dishId, body)
            } finally { await this.reload() }
        },

        // QĐ3-11: this dish gets its own copy of a shared group, in the same place
        async copyOptionGroup(dishId, groupId, body) {
            const dish = this.allItems.find(i => i.id === dishId)
            try {
                await copyGroupForDish(apiSellerMenu, dishId, (dish?.option_groups || []).map(g => g.id), groupId, body)
            } finally { await this.reload() }
        },

        // A group still on dishes is taken off them first: the API deletes only an unused group
        async deleteOptionGroup(groupId, dishIds = []) {
            try {
                for (const dishId of dishIds) await apiSellerMenu.detachOptionGroup(dishId, groupId)
                await apiSellerMenu.deleteOptionGroup(groupId)
            } finally { await this.reload() }
        },

        async attachOptionGroup(dishId, groupId) {
            try { await apiSellerMenu.attachOptionGroup(dishId, groupId) } finally { await this.reload() }
        },

        async detachOptionGroup(dishId, groupId) {
            try { await apiSellerMenu.detachOptionGroup(dishId, groupId) } finally { await this.reload() }
        },

        // ── Image upload (via backend, service role) ─────────────────────────

        async uploadImage(itemId, file) {
            const imageBase64 = await fileToBase64(file)
            const res = await apiSellerMenu.uploadItemImage(itemId, imageBase64, file.type)
            return res.image_url
        },
    },
})
