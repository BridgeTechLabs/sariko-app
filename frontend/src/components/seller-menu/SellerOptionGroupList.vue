<script>
import { useMenuStore } from '@/stores/seller/menuStore'
import { Pencil, Trash2 } from 'lucide-vue-next'
import ModalEditOptionGroup from './ModalEditOptionGroup.vue'

// The "Option groups" tab (seller-menu đợt 3): every group of the store, to rename it, change prices or switch off
// an option that ran out. Groups are made from a dish (Q4), so there is no add button here.
export default {
    name: 'SellerOptionGroupList',

    components: { ModalEditOptionGroup, Pencil, Trash2 },

    data() {
        return { showForm: false, editing: null, deleting: null, busy: false }
    },

    computed: {
        store() { return useMenuStore() },
        groups() { return this.store.optionGroups },
    },

    methods: {
        dishList(g) { return this.store.dishNames(g.dish_ids) },
        edit(g) {
            this.editing = g
            this.showForm = true
        },
        // A group still on dishes is taken off them first (the API deletes only an unused group)
        async confirmDelete() {
            this.busy = true
            try {
                await this.store.deleteOptionGroup(this.deleting.id, this.deleting.dish_ids)
                this.$q.notify({ classes: 'quasar-notify-positive', message: this.$t('seller_menu.toast_group_deleted'), position: 'bottom', timeout: 1500 })
            } catch (e) {
                // API errors are toasted by axiosPolicy
                console.error('SellerOptionGroupList - delete -', e)
                if (!e.response) this.$q.notify({ type: 'negative', message: this.$t('seller_menu.toast_delete_failed'), position: 'bottom' })
            } finally {
                this.busy = false
                this.deleting = null
            }
        },
    },
}
</script>

<template>
    <div class="og-list">
        <div v-if="!groups.length" class="empty">
            <div class="empty-title">{{ $t('seller_menu.og_empty') }}</div>
            <div class="empty-sub">{{ $t('seller_menu.og_empty_sub') }}</div>
        </div>

        <div v-for="g in groups" :key="g.id" class="og-card" @click="edit(g)">
            <div class="og-head">
                <div class="og-name">{{ g.name }}</div>
                <div class="og-actions" @click.stop>
                    <button class="btn-icon" :aria-label="$t('seller_menu.og_edit_title')" :title="$t('seller_menu.og_edit_title')" @click="edit(g)">
                        <span class="icon-box"><Pencil :size="15" /></span>
                    </button>
                    <button class="btn-icon btn-icon--trash" :aria-label="$t('seller_menu.og_delete')" :title="$t('seller_menu.og_delete')" @click="deleting = g">
                        <span class="icon-box"><Trash2 :size="15" /></span>
                    </button>
                </div>
            </div>
            <div class="og-tags">
                <span class="chip" :class="{ 'chip--required': g.is_required }">
                    {{ $t(g.is_required ? 'food_detail_page.options_required' : 'food_detail_page.options_optional') }}
                </span>
                <span class="chip">
                    {{ g.max_select > 1 ? $t('food_detail_page.options_up_to', { n: g.max_select }) : $t('food_detail_page.options_choose_one') }}
                </span>
                <span class="chip">{{ $t('seller_menu.og_option_count', g.menu_options.length) }}</span>
            </div>
            <!-- one dish per line, at most 3 then "+N more": the card tells a much-used group without
                 growing past 4 names; the group form lists them all (Jack 13/11) -->
            <div class="og-used">
                <template v-if="g.dish_ids.length">
                    <div>{{ $t('seller_menu.og_used_in', g.dish_ids.length) }}</div>
                    <div v-for="(name, n) in dishList(g).slice(0, 3)" :key="n" class="og-dish">{{ name }}</div>
                    <div v-if="g.dish_ids.length > 3" class="og-dish og-dish--more">{{ $t('seller_menu.og_more', { n: g.dish_ids.length - 3 }) }}</div>
                </template>
                <template v-else>{{ $t('seller_menu.og_not_used') }}</template>
            </div>
        </div>

        <ModalEditOptionGroup v-model="showForm" :group="editing" />

        <q-dialog :model-value="!!deleting" @update:model-value="v => !v && (deleting = null)">
            <q-card v-if="deleting" class="confirm-dialog">
                <q-card-section>
                    <div class="dialog-title">{{ $t('seller_menu.og_delete_named_title', { name: deleting.name }) }}</div>
                    <div class="dialog-sub">
                        {{ deleting.dish_ids.length ? $t('seller_menu.og_delete_used_body', { names: dishList(deleting).join(', ') }) : $t('seller_menu.og_delete_confirm_body') }}
                    </div>
                </q-card-section>
                <q-card-actions align="right">
                    <q-btn flat no-caps :label="$t('common.button_label_cancel')" v-close-popup />
                    <q-btn flat no-caps color="negative" :loading="busy" @click="confirmDelete">{{ $t('seller_menu.og_delete') }}</q-btn>
                </q-card-actions>
            </q-card>
        </q-dialog>
    </div>
</template>

<style lang="scss" scoped>
.og-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding-top: 14px;
}

.og-card {
    padding: 12px 12px 13px;   /* the last line ends as far from the bottom edge as the name starts from the top */
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    cursor: pointer;
}

.og-head {
    display: flex;
    align-items: center;
    gap: 4px;
    margin: -10px -10px 0 0;   /* the 44px icon buttons reach into the card's padding; the name keeps the same gap as the bottom */
}

.og-name { flex: 1; min-width: 0; font-size: 15px; font-weight: 600; color: var(--text-primary); overflow-wrap: anywhere; }

.og-actions { display: flex; flex-shrink: 0; }

/* 44px to tap, the 30px box looks like the category title's icons */
.btn-icon {
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    padding: 0;
    color: var(--text-secondary);
    cursor: pointer;
}

.btn-icon--trash { color: #f87171; }

.icon-box {
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255,255,255,0.07);
    border-radius: 8px;
}

.confirm-dialog {
    background: #1f2940;
    border-radius: 16px;
    min-width: 280px;
    color: var(--text-primary);
}

.dialog-title { font-size: 17px; font-weight: 700; margin-bottom: 4px; }
.dialog-sub   { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }

.og-tags {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin-top: 2px;
}

.chip {
    font-size: 11px;
    font-weight: 600;
    line-height: 20px;
    padding: 0 8px;
    border-radius: 6px;
    background: rgba(255,255,255,0.08);
    color: var(--text-secondary);
}

.chip--required { background: var(--accent-dim, rgba(250,204,21,0.12)); color: var(--color-accent); }

.og-used {
    margin-top: 10px;
    font-size: 12px;
    line-height: 1.5;
    color: var(--text-muted);
    overflow-wrap: anywhere;
}

.og-dish {
    padding-left: 12px;
    font-size: 13px;
    color: var(--text-secondary);
}

.og-dish--more { font-size: 12px; color: var(--text-muted); }


.empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 48px 20px;
    text-align: center;
}

.empty-title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.empty-sub { font-size: 13px; color: var(--text-muted); }
</style>
