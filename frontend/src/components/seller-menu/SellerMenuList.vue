<script>
import { useMenuStore } from '@/stores/seller/menuStore'
import SellerMenuCategorySection from './SellerMenuCategorySection.vue'
import ModalEditCategory from './ModalEditCategory.vue'
import ModalEditItem from './ModalEditItem.vue'
import SellerOptionGroupList from './SellerOptionGroupList.vue'
import { Plus } from 'lucide-vue-next'

export default {
    name: 'SellerMenuList',

    components: { SellerMenuCategorySection, ModalEditCategory, ModalEditItem, SellerOptionGroupList, Plus },

    data() {
        return {
            showAddCategory: false,
            showAddItem: false,
            tab: 'dishes',   // or 'groups' (seller-menu đợt 3)
        }
    },

    computed: {
        store()       { return useMenuStore() },
        categories()  { return this.store.categories },
        isLoading()   { return this.store.isLoading },
        loadError()   { return this.store.loadError },
    },

    async mounted() {
        await this.fetchMenu()
    },

    methods: {
        fetchMenu() { return this.store.fetchMenu() },
    },
}
</script>

<template>
    <div>
        <q-tabs v-model="tab" dense no-caps align="justify" class="menu-tabs">
            <q-tab name="dishes" :label="$t('seller_menu.tab_dishes')" />
            <q-tab name="groups" :label="$t('seller_menu.tab_option_groups')" />
        </q-tabs>

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

        <SellerOptionGroupList v-else-if="tab === 'groups' && !loadError" />

        <!-- Load failed: not the same as an empty menu -->
        <div v-else-if="loadError" class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div class="empty-title">{{ $t('seller_menu.load_error') }}</div>
            <div class="empty-sub">{{ $t('seller_menu.load_error_sub') }}</div>
            <button class="btn-empty-add" @click="fetchMenu()">
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

        <!-- Fixed bar just above the bottom nav; the list keeps a bottom pad of its height -->
        <div v-if="tab === 'dishes' && !isLoading && !loadError && categories.length" class="add-bar">
            <button class="btn-add-dish" @click="showAddItem = true">
                <Plus :size="16" /> {{ $t('seller_menu.item_add_dish') }}
            </button>
            <button class="btn-add-category" @click="showAddCategory = true">
                <Plus :size="16" /> {{ $t('seller_menu.category_add') }}
            </button>
        </div>


        <ModalEditCategory v-model="showAddCategory" :category="null" />
        <ModalEditItem v-model="showAddItem" />
    </div>
</template>

<style lang="scss" scoped>
.menu-tabs {
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--bg-main);
    color: var(--text-secondary);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    :deep(.q-tab) { min-height: 44px; font-size: 15px; }
    :deep(.q-tab--active) { color: var(--color-accent); font-weight: 600; }
    :deep(.q-tab__indicator) { background: var(--color-accent); height: 2px; }
}

/* Skeleton */
.skeleton-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.sk-section {
    padding: 14px 0 0;
}

.sk-item-row {
    display: flex;
    gap: 12px;
    margin-bottom: 10px;
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
    padding-top: 14px;
    padding-bottom: 72px;   /* the fixed add bar's height */
}

.add-bar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: var(--bottom-nav-height, 72px);
    z-index: 5;
    display: flex;
    gap: 10px;
    padding: 12px 16px 14px;
    background: linear-gradient(to top, var(--bg-main) 70%, transparent);
}

.btn-add-dish, .btn-add-category {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 13px;
    border-radius: 12px;
    font-size: 15px;
    font-family: inherit;
    cursor: pointer;
}

.btn-add-dish {
    background: var(--color-accent);
    color: #121b2f;
    border: none;
    font-weight: 700;
}

.btn-add-category {
    background: none;
    border: 1px solid rgba(255,255,255,0.25);
    color: var(--text-primary);
    font-weight: 600;
}
</style>
