<script>
import { ChevronUp, ChevronDown, Pencil, Trash2 } from 'lucide-vue-next'
import { useMenuStore } from '@/stores/seller/menuStore'
import SellerMenuFoodItem from './SellerMenuFoodItem.vue'
import ModalEditCategory from './ModalEditCategory.vue'

export default {
    name: 'SellerMenuCategorySection',

    components: { ChevronUp, ChevronDown, Pencil, Trash2, SellerMenuFoodItem, ModalEditCategory },

    props: {
        category: { type: Object, required: true },
    },

    data() {
        return {
            showEditCategory: false,
            expanded: true,
            showDeleteConfirm: false,
            deleting: false,
        }
    },

    methods: {
        onDeleteClick() {
            const count = (this.category.food_items || []).length
            if (count > 0) {
                this.$q.notify({ type: 'warning', message: this.$t('seller_menu.category_delete_has_items', { count }), position: 'bottom' })
                return
            }
            this.showDeleteConfirm = true
        },

        async confirmDelete() {
            this.deleting = true
            try {
                await useMenuStore().deleteCategory(this.category.id)
                this.showDeleteConfirm = false
            } catch (e) {
                console.error('SellerMenuCategorySection - confirmDelete -', e)
                this.$q.notify({ type: 'negative', message: this.$t('seller_menu.toast_delete_failed'), position: 'bottom' })
            } finally {
                this.deleting = false
            }
        },
    },
}
</script>

<template>
    <div class="category-section">
        <div class="category-header" @click="expanded = !expanded">
            <div class="category-left">
                <span class="category-name">{{ category.name }}</span>
                <span class="item-count">{{ $t('seller_menu.dish_count', (category.food_items || []).length, { count: (category.food_items || []).length }) }}</span>
            </div>
            <div class="category-actions" @click.stop>
                <button class="btn-cat-icon" :aria-label="$t('seller_menu.category_edit_label')" :title="$t('seller_menu.category_edit_label')" @click="showEditCategory = true">
                    <Pencil :size="15" />
                </button>
                <button class="btn-cat-icon btn-cat-trash" :aria-label="$t('seller_menu.category_delete_label')" :title="$t('seller_menu.category_delete_label')" @click="onDeleteClick">
                    <Trash2 :size="15" />
                </button>
                <button class="btn-cat-fold" :aria-label="$t(expanded ? 'seller_menu.category_collapse' : 'seller_menu.category_expand')" @click="expanded = !expanded">
                    <ChevronUp v-if="expanded" :size="16" />
                    <ChevronDown v-else :size="16" />
                </button>
            </div>
        </div>

        <div v-if="expanded">
            <div v-if="(category.food_items || []).length === 0" class="empty-cat">
                {{ $t('seller_menu.category_empty') }}
            </div>
            <SellerMenuFoodItem
                v-for="item in category.food_items"
                :key="item.id"
                :item="item"
            />
        </div>

        <ModalEditCategory v-model="showEditCategory" :category="category" />
        <q-dialog v-model="showDeleteConfirm">
            <q-card class="confirm-dialog">
                <q-card-section>
                    <div class="dialog-title">{{ $t('seller_menu.category_delete_confirm_title') }}</div>
                    <div class="dialog-sub">{{ $t('seller_menu.category_delete_confirm_body') }}</div>
                </q-card-section>
                <q-card-actions align="right">
                    <q-btn flat no-caps :label="$t('common.button_label_cancel')" v-close-popup />
                    <q-btn flat no-caps color="negative" :loading="deleting" @click="confirmDelete">
                        {{ $t('seller_menu.category_delete_confirm_action') }}
                    </q-btn>
                </q-card-actions>
            </q-card>
        </q-dialog>
    </div>
</template>

<style lang="scss" scoped>
.category-section {
    margin-bottom: 16px;   /* + the last card's 14px = 30px above the next title */
}

.category-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 0 28px;
    cursor: pointer;
    user-select: none;
}

.category-left {
    display: flex;
    align-items: baseline;
    gap: 8px;
    flex: 1;
    min-width: 0;
}

.category-name {
    min-width: 0;
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.item-count {
    font-size: 14px;
    color: var(--text-muted);
    flex-shrink: 0;
}

.category-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
    margin-left: 10px;
}

.btn-cat-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    color: var(--text-secondary);
    background: rgba(255,255,255,0.07);
    border: none;
    border-radius: 8px;
    cursor: pointer;
}

.btn-cat-trash { color: #f87171; }

.confirm-dialog {
    background: #1f2940;
    border-radius: 16px;
    min-width: 280px;
    color: var(--text-primary);
}

.dialog-title { font-size: 17px; font-weight: 700; margin-bottom: 4px; }
.dialog-sub   { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }

.btn-cat-fold {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    color: var(--text-secondary);
    background: rgba(255,255,255,0.1);
    border: none;
    border-radius: 50%;
    cursor: pointer;
}

.empty-cat {
    font-size: 13px;
    color: var(--text-muted);
    text-align: center;
    padding: 16px 0;
}
</style>
