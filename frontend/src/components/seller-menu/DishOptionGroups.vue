<script>
import { useMenuStore } from '@/stores/seller/menuStore'
import { X, Plus } from 'lucide-vue-next'
import SectionTitle from '@/components/shared/SectionTitle.vue'
import ModalEditOptionGroup from './ModalEditOptionGroup.vue'

// The OPTIONS part of the dish form (seller-menu đợt 3, Q4: groups are managed from a dish): the dish's groups
// in order, tap one to edit it, x takes it off this dish; "+ Add option group" creates one or reuses one the store has.
// Each change is saved at once (the group form has its own Save), so a new dish needs saving first.
export default {
    name: 'DishOptionGroups',

    components: { X, Plus, SectionTitle, ModalEditOptionGroup },

    props: {
        dishId: { type: String, default: null },   // null = a dish not saved yet
    },

    data() {
        return { showPicker: false, showForm: false, editing: null, busy: false }
    },

    computed: {
        store() { return useMenuStore() },
        limits() { return this.store.optionLimits },
        dish() { return this.store.allItems.find(i => i.id === this.dishId) },
        groups() { return this.dish?.option_groups || [] },
        // The store's groups not on this dish yet
        others() { return this.store.optionGroups.filter(g => !this.groups.some(d => d.id === g.id)) },
        atDishMax() { return this.groups.length >= this.limits.menu_max_groups_per_dish },
        atStoreMax() { return this.store.optionGroups.length >= this.limits.menu_max_groups_per_store },
    },

    methods: {
        summary(g) {
            const pick = g.max_select > 1 ? this.$t('food_detail_page.options_up_to', { n: g.max_select }) : this.$t('food_detail_page.options_choose_one')
            const need = this.$t(g.is_required ? 'food_detail_page.options_required' : 'food_detail_page.options_optional')
            return [need, pick, this.$t('seller_menu.og_option_count', g.menu_options.length)].join(' · ')
        },

        // The dish's embed has no dish_ids: the form gets the store's copy of the group
        edit(g) {
            this.editing = this.store.optionGroups.find(s => s.id === g.id) || null
            this.showForm = true
        },

        create() {
            this.showPicker = false
            this.editing = null
            this.showForm = true
        },

        async run(call) {
            this.busy = true
            try {
                await call()
            } catch (e) {
                // API errors are toasted by axiosPolicy
                console.error('DishOptionGroups -', e)
                if (!e.response) this.$q.notify({ type: 'negative', message: this.$t('seller_menu.toast_save_failed'), position: 'bottom' })
            } finally {
                this.busy = false
            }
        },

        attach(g) {
            this.showPicker = false
            return this.run(() => this.store.attachOptionGroup(this.dishId, g.id))
        },

        remove(g) { return this.run(() => this.store.detachOptionGroup(this.dishId, g.id)) },
    },
}
</script>

<template>
    <div class="dish-options">
        <SectionTitle>{{ $t('seller_menu.group_options') }}</SectionTitle>

        <div v-if="!dishId" class="hint">{{ $t('seller_menu.options_save_first') }}</div>
        <template v-else>
            <div v-for="g in groups" :key="g.id" class="og-row" @click="edit(g)">
                <div class="og-text">
                    <div class="og-name">{{ g.name }}</div>
                    <div class="og-sub">{{ summary(g) }}</div>
                </div>
                <button class="btn-icon" :disabled="busy" :aria-label="$t('seller_menu.og_remove_from_dish')" @click.stop="remove(g)"><X :size="16" /></button>
            </div>
            <button class="btn-dashed" :disabled="atDishMax || busy" @click="showPicker = true">
                <Plus :size="16" /> {{ $t('seller_menu.options_add_group') }}
            </button>
            <div class="hint">
                {{ atDishMax ? $t('api_errors.groups_per_dish_max', { max: limits.menu_max_groups_per_dish }) : $t('seller_menu.options_hint') }}
            </div>
        </template>

        <!-- "+ Add option group": a new group, or one the store already has -->
        <q-dialog v-model="showPicker" position="bottom" full-width>
            <q-card class="picker">
                <div class="picker-handle" />
                <div class="picker-title">{{ $t('seller_menu.tab_option_groups') }}</div>
                <div class="picker-sub">{{ dish?.name }}</div>

                <button class="create-card" :disabled="atStoreMax" @click="create">
                    <span class="create-icon"><Plus :size="18" /></span>
                    <span>
                        <span class="create-title">{{ $t('seller_menu.og_create') }}</span>
                        <span class="create-sub">{{ atStoreMax ? $t('api_errors.groups_per_store_max', { max: limits.menu_max_groups_per_store }) : $t('seller_menu.og_create_sub') }}</span>
                    </span>
                </button>

                <template v-if="others.length">
                    <div class="picker-section">{{ $t('seller_menu.og_existing') }}</div>
                    <div class="picker-hint">{{ $t('seller_menu.og_existing_hint') }}</div>
                    <button v-for="g in others" :key="g.id" class="existing-row" @click="attach(g)">
                        <span class="existing-name">{{ g.name }}</span>
                        <span class="existing-sub">
                            {{ $t('seller_menu.og_option_count', g.menu_options.length) }} ·
                            {{ g.dish_ids.length ? $t('seller_menu.og_in_dishes', g.dish_ids.length) : $t('seller_menu.og_not_used') }}
                        </span>
                    </button>
                </template>

                <q-btn flat no-caps class="picker-cancel" :label="$t('common.button_label_cancel')" v-close-popup />
            </q-card>
        </q-dialog>

        <ModalEditOptionGroup v-model="showForm" :group="editing" :dish-id="dishId" />
    </div>
</template>

<style lang="scss" scoped>
.dish-options {
    display: flex;
    flex-direction: column;
    gap: 8px;
    :deep(.section-title) { margin-bottom: 0; }
}

.hint {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.4;
}

.og-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 4px 10px 12px;
    background: rgba(255,255,255,0.05);
    border-radius: 10px;
    cursor: pointer;
}

.og-text { flex: 1; min-width: 0; }
.og-name { font-size: 14px; overflow-wrap: anywhere; }
.og-sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

.btn-icon {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
}

.btn-dashed {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 100%;
    min-height: 40px;
    background: none;
    border: 1px dashed rgba(255,255,255,0.2);
    border-radius: 10px;
    color: var(--text-muted);
    font-family: inherit;
    font-size: 13px;
    cursor: pointer;
    &:disabled { opacity: 0.4; cursor: default; }
}

.picker {
    background: #1f2940;
    border-radius: 20px 20px 0 0;
    color: var(--text-primary);
    max-height: 80vh;
    overflow-y: auto;
    padding: 8px 16px calc(8px + env(safe-area-inset-bottom, 0));
    display: flex;
    flex-direction: column;
}

.picker-handle {
    width: 40px;
    height: 4px;
    border-radius: 2px;
    background: rgba(255,255,255,0.2);
    margin: 0 auto 12px;
}

.picker-title { font-size: 17px; font-weight: 700; }
.picker-sub { font-size: 12px; color: var(--text-muted); margin-bottom: 12px; }

.create-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px;
    text-align: left;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--color-accent);
    border-radius: 12px;
    color: var(--text-primary);
    font-family: inherit;
    cursor: pointer;
    &:disabled { opacity: 0.5; cursor: default; }
}

.create-icon {
    width: 36px;
    height: 36px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    background: var(--accent-dim, rgba(250,204,21,0.12));
    color: var(--color-accent);
}

.create-title { display: block; font-size: 15px; font-weight: 600; }
.create-sub { display: block; font-size: 12px; color: var(--text-muted); }

.picker-section {
    margin-top: 16px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.picker-hint { font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }

.existing-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 48px;
    padding: 0;
    background: none;
    border: none;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    color: var(--text-primary);
    font-family: inherit;
    font-size: 14px;
    text-align: left;
    cursor: pointer;
}

.existing-name { overflow-wrap: anywhere; }
.existing-sub { flex-shrink: 0; font-size: 12px; color: var(--text-muted); }

.picker-cancel { margin-top: 8px; color: var(--text-secondary); }
</style>
