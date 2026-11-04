<script>
import { useMenuStore } from '@/stores/seller/menuStore'
import LayoutSellerMenu from '@/layouts/seller/LayoutSellerMenu.vue'
import SellerMenuCategorySection from '@/components/seller-menu/SellerMenuCategorySection.vue'
import ModalEditCategory from '@/components/seller-menu/ModalEditCategory.vue'
import ModalEditItem from '@/components/seller-menu/ModalEditItem.vue'
import PageBreadcrumbs from '@/components/shared/PageBreadcrumbs.vue'
import { Plus } from 'lucide-vue-next'

export default {
    name: 'SellerMenuPage',

    components: { LayoutSellerMenu, SellerMenuCategorySection, ModalEditCategory, ModalEditItem, PageBreadcrumbs, Plus },

    data() {
        return {
            showAddCategory: false,
            showAddItem: false,
        }
    },

    computed: {
        store()       { return useMenuStore() },
        categories()  { return this.store.categories },
        isLoading()   { return this.store.isLoading },
        loadError()   { return this.store.loadError },
        totalItems()  { return this.store.allItems.length },
    },

    async mounted() {
        await useMenuStore().fetchMenu()
    },
}
</script>

<template>
    <LayoutSellerMenu>

        <template #Header>
            <div class="page-header">
                <PageBreadcrumbs :title="$t('seller_menu.page_title')" />
                <div class="header-actions">
                    <button class="btn-add-cat" @click="showAddCategory = true">
                        <Plus :size="14" />
                        {{ $t('seller_menu.category_add') }}
                    </button>
                    <button class="btn-add-item" @click="showAddItem = true">
                        <Plus :size="14" />
                        {{ $t('seller_menu.item_add') }}
                    </button>
                </div>
            </div>
        </template>

        <template #Content>

            <!-- Loading -->
            <div v-if="isLoading" class="skeleton-list">
                <div v-for="n in 3" :key="n" class="sk-section">
                    <q-skeleton type="text" width="120px" height="18px" animation="pulse" style="margin-bottom:12px;" />
                    <div v-for="i in 2" :key="i" class="sk-item-row">
                        <q-skeleton type="rect" width="52px" height="52px" style="border-radius:10px;" animation="pulse" />
                        <div class="sk-item-info">
                            <q-skeleton type="text" width="130px" height="15px" animation="pulse" />
                            <q-skeleton type="text" width="70px" height="13px" animation="pulse" style="margin-top:5px;" />
                        </div>
                    </div>
                </div>
            </div>

            <!-- Load failed: not the same as an empty menu -->
            <div v-else-if="loadError" class="empty-state">
                <div class="empty-icon">⚠️</div>
                <div class="empty-title">{{ $t('seller_menu.load_error') }}</div>
                <div class="empty-sub">{{ $t('seller_menu.load_error_sub') }}</div>
                <button class="btn-empty-add" @click="store.fetchMenu()">
                    {{ $t('seller_menu.retry') }}
                </button>
            </div>

            <!-- Empty state -->
            <div v-else-if="categories.length === 0" class="empty-state">
                <div class="empty-icon">🍽️</div>
                <div class="empty-title">{{ $t('seller_menu.empty_title') }}</div>
                <div class="empty-sub">{{ $t('seller_menu.empty_sub') }}</div>
                <button class="btn-empty-add" @click="showAddCategory = true">
                    <Plus :size="15" style="margin-right:6px;" />
                    {{ $t('seller_menu.category_add') }}
                </button>
            </div>

            <!-- Category list -->
            <div v-else class="categories-list">
                <SellerMenuCategorySection
                    v-for="cat in categories"
                    :key="cat.id"
                    :category="cat"
                />
            </div>

        </template>

    </LayoutSellerMenu>

    <ModalEditCategory v-model="showAddCategory" :category="null" />
    <ModalEditItem v-model="showAddItem" />
</template>

<style lang="scss" scoped>
.page-header {
    padding: 12px 16px 8px;
}

.header-actions {
    display: flex;
    gap: 8px;
    margin-top: 12px;
}

.btn-add-cat, .btn-add-item {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 10px;
    padding: 8px 14px;
    cursor: pointer;
    font-family: inherit;
    border: none;
    transition: opacity 0.15s;
    &:active { opacity: 0.75; }
}

.btn-add-cat {
    background: rgba(255,255,255,0.08);
    color: var(--text-primary);
    border: 1px solid rgba(255,255,255,0.12);
}

.btn-add-item {
    background: var(--color-accent);
    color: #121b2f;
}

/* Skeleton */
.skeleton-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.sk-section {
    background: rgba(255,255,255,0.05);
    border-radius: 16px;
    padding: 14px;
}

.sk-item-row {
    display: flex;
    gap: 12px;
    margin-bottom: 12px;
    &:last-child { margin-bottom: 0; }
}

.sk-item-info { flex: 1; }

/* Empty state */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 60px 20px;
    gap: 8px;
}

.empty-icon { font-size: 48px; margin-bottom: 4px; }

.empty-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
}

.empty-sub {
    font-size: 13px;
    color: var(--text-muted);
    text-align: center;
}

.btn-empty-add {
    display: flex;
    align-items: center;
    margin-top: 12px;
    background: var(--color-accent);
    color: #121b2f;
    font-weight: 700;
    font-size: 14px;
    border: none;
    border-radius: 12px;
    padding: 10px 20px;
    cursor: pointer;
    font-family: inherit;
}

.categories-list {
    padding-top: 8px;
}
</style>
