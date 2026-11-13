<script>
import { useMenuStore } from '@/stores/seller/menuStore'
import { X, Plus } from 'lucide-vue-next'
import { formatVnd } from '@/utils/priceDisplay'

// One option group (seller-menu đợt 3, mockup "Edit option group"): name, required or not, choose 1 or up to N,
// the options (name, extra price, on / off). Saving changes the group on every dish using it.
// From a dish (dishId): "Remove from this dish", and for a group on 2+ dishes "Edit for this dish only" (QĐ3-11).
// From the Option groups tab: "Delete group" for a group no dish uses (QĐ3-7).
export default {
    name: 'ModalEditOptionGroup',

    components: { X, Plus },

    props: {
        modelValue: { type: Boolean, default: false },
        group: { type: Object, default: null },    // a store group (with dish_ids); null = a new group for dishId
        dishId: { type: String, default: null },   // opened from this dish's form
    },

    emits: ['update:modelValue'],

    data() {
        return {
            form: { name: '', is_required: true, max_select: 1, options: [] },
            copy: false,       // editing a copy for this dish only (QĐ3-11): nothing is written until Save
            upTo: false,       // "Up to N" picked: drives the radios and the number box, whatever is typed in it
            saving: false,
            showSoldOut: false,
            showDelete: false,
        }
    },

    computed: {
        store() { return useMenuStore() },
        limits() { return this.store.optionLimits },
        isNew() { return !this.group || this.copy },
        // The dishes this save changes
        dishIds() { return this.isNew ? [this.dishId] : this.group.dish_ids },
        dishNames() { return this.store.dishNames(this.dishIds).join(', ') },
        shared() { return !this.isNew && this.group.dish_ids.length >= 2 },
        atOptionsMax() { return this.form.options.length >= this.limits.menu_max_options_per_group },
        canSave() {
            return this.form.name.trim() && this.form.options.length && this.form.options.every(o => o.name.trim() && !this.overCap(o))
                && (this.upTo ? this.form.max_select >= 2 : true) && !this.saving
        },
        // A required group with every option off: the dishes using it show as sold out (QĐ3-6)
        soldOut() {
            return this.form.is_required && this.form.options.every(o => !o.is_available) && this.dishIds.length > 0
        },
    },

    watch: {
        modelValue(open) { if (open) this.reset() },
    },

    methods: {
        formatVnd,

        reset() {
            this.copy = false
            const g = this.group
            this.upTo = g?.max_select > 1
            this.form = g
                ? { name: g.name, is_required: g.is_required, max_select: g.max_select,
                    options: g.menu_options.map(o => ({ id: o.id, name: o.name, extra_price: Number(o.extra_price) || null, is_available: o.is_available })) }
                : { name: '', is_required: true, max_select: 1, options: [{ id: null, name: '', extra_price: null, is_available: true }] }
        },

        // The cap holds for a new or changed price; a price saved under a higher cap stays (TC3-67)
        overCap(o) {
            const old = !this.copy && this.group?.menu_options.find(x => x.id === o.id)   // a copy's prices are all new
            return o.extra_price > this.limits.menu_option_max_extra_price && (!old || Number(old.extra_price) !== o.extra_price)
        },

        setLimit(upTo) {
            this.upTo = upTo
            this.form.max_select = upTo ? Math.max(2, Number(this.form.max_select) || 0) : 1
        },

        addOption() { this.form.options.push({ id: null, name: '', extra_price: null, is_available: true }) },

        close() { this.$emit('update:modelValue', false) },

        async save(confirmed = false) {
            if (!this.canSave) return
            if (this.soldOut && !confirmed) { this.showSoldOut = true; return }
            this.showSoldOut = false
            const body = {
                name: this.form.name.trim(),
                is_required: this.form.is_required,
                max_select: this.form.max_select,
                options: this.form.options.map(o => ({
                    id: this.copy ? undefined : o.id || undefined,   // a copy's options are new rows
                    name: o.name.trim(), extra_price: o.extra_price || 0, is_available: o.is_available,
                })),
            }
            await this.run(() => this.copy
                ? this.store.copyOptionGroup(this.dishId, this.group.id, body)
                : this.store.saveOptionGroup(this.group?.id, body, this.dishId), 'toast_group_saved')
        },

        removeFromDish() {
            return this.run(() => this.store.detachOptionGroup(this.dishId, this.group.id), 'toast_group_removed')
        },

        deleteGroup() {
            this.showDelete = false
            return this.run(() => this.store.deleteOptionGroup(this.group.id), 'toast_group_deleted')
        },

        // API errors (caps, same option name, ...) are toasted by axiosPolicy in the seller's language
        async run(call, doneKey) {
            this.saving = true
            try {
                await call()
                this.$q.notify({ classes: 'quasar-notify-positive', message: this.$t(`seller_menu.${doneKey}`), position: 'bottom', timeout: 1500 })
                this.close()
            } catch (e) {
                console.error('ModalEditOptionGroup -', e)
                if (!e.response) this.$q.notify({ type: 'negative', message: this.$t('seller_menu.toast_save_failed'), position: 'bottom' })
            } finally {
                this.saving = false
            }
        },
    },
}
</script>

<template>
    <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" position="bottom" full-width>
        <q-card class="og-sheet">
            <div class="sheet-header">
                <span class="sheet-title">{{ $t(copy ? 'seller_menu.og_copy_title' : group ? 'seller_menu.og_edit_title' : 'seller_menu.og_new_title') }}</span>
                <button class="btn-close" :aria-label="$t('common.button_label_close')" @click="close"><X :size="20" /></button>
            </div>

            <div class="sheet-body">
                <div>
                    <div class="field-label">{{ $t('seller_menu.og_name') }} *</div>
                    <q-input v-model="form.name" dense outlined dark maxlength="60" />
                    <div class="hint">{{ $t('seller_menu.og_name_hint') }}</div>
                </div>

                <!-- Questions to the seller, one radio row each answer (Jack 13/11); the number sits on the "Up to" row -->
                <div>
                    <div class="question">{{ $t('seller_menu.og_requirement') }}</div>
                    <div class="radio-rows">
                        <q-radio v-model="form.is_required" :val="true" dark color="amber" class="radio-row" :label="$t('food_detail_page.options_required')" />
                        <q-radio v-model="form.is_required" :val="false" dark color="amber" class="radio-row" :label="$t('food_detail_page.options_optional')" />
                    </div>
                </div>

                <div>
                    <div class="question">{{ $t('seller_menu.og_limit') }}</div>
                    <div class="radio-rows">
                        <q-radio :model-value="upTo" :val="false" dark color="amber" class="radio-row" :label="$t('seller_menu.og_exactly_one')" @update:model-value="setLimit" />
                        <div class="radio-row radio-row--input">
                            <q-radio :model-value="upTo" :val="true" dark color="amber" class="radio-grow" :label="$t('seller_menu.og_up_to')" @update:model-value="setLimit" />
                            <q-input v-if="upTo" v-model.number="form.max_select" dense outlined dark type="number" min="2" step="1"
                                inputmode="numeric" class="max-input" :aria-label="$t('seller_menu.og_up_to')" />
                        </div>
                    </div>
                </div>

                <div>
                    <div class="field-label">{{ $t('seller_menu.og_options') }} *</div>
                    <div class="option-list">
                        <div v-for="(o, n) in form.options" :key="n" class="option-row">
                            <q-input v-model="o.name" dense outlined dark maxlength="60" class="option-name" :placeholder="$t('seller_menu.og_option_name')" />
                            <q-input :model-value="o.extra_price" dense outlined dark inputmode="numeric" class="option-price"
                                mask="#.###.###" reverse-fill-mask unmasked-value :prefix="o.extra_price ? '+' : undefined" :suffix="o.extra_price ? '₫' : undefined"
                                :placeholder="$t('seller_menu.og_free')"
                                :error="overCap(o)" hide-bottom-space
                                @update:model-value="v => (o.extra_price = v ? Number(v) : null)" />
                            <q-toggle v-model="o.is_available" dense color="positive" :aria-label="$t('seller_menu.og_option_on')" />
                            <button class="btn-icon" :disabled="form.options.length === 1" :aria-label="$t('seller_menu.og_option_remove')"
                                @click="form.options.splice(n, 1)"><X :size="16" /></button>
                        </div>
                    </div>
                    <button class="btn-dashed" :disabled="atOptionsMax" @click="addOption"><Plus :size="16" /> {{ $t('seller_menu.og_add_option') }}</button>
                    <div v-if="form.options.some(overCap)" class="hint hint--error">
                        {{ $t('seller_menu.og_price_max', { price: formatVnd(limits.menu_option_max_extra_price) }) }}
                    </div>
                    <div class="hint">
                        {{ atOptionsMax ? $t('api_errors.options_max', { max: limits.menu_max_options_per_group, count: limits.menu_max_options_per_group }) : $t('seller_menu.og_options_hint') }}
                    </div>
                </div>

                <div v-if="copy" class="note">{{ $t('seller_menu.og_copy_note') }}</div>
                <div v-else-if="shared" class="note">
                    {{ $t('seller_menu.og_shared_note', { n: group.dish_ids.length, names: dishNames }) }}
                    <button v-if="dishId" class="btn-copy" @click="copy = true">{{ $t('seller_menu.og_edit_this_dish_only') }}</button>
                </div>
                <div v-else-if="group && !group.dish_ids.length" class="hint">{{ $t('seller_menu.og_not_used') }}</div>
            </div>

            <div class="sheet-footer">
                <q-btn unelevated no-caps class="btn-save" :disable="!canSave" :loading="saving" @click="save()">{{ $t('seller_menu.og_save') }}</q-btn>
                <q-btn v-if="dishId && group && !copy" flat no-caps class="btn-danger" :disable="saving" @click="removeFromDish">
                    {{ $t('seller_menu.og_remove_from_dish') }}
                </q-btn>
                <q-btn v-if="!dishId && group && !group.dish_ids.length" flat no-caps class="btn-danger" :disable="saving" @click="showDelete = true">
                    {{ $t('seller_menu.og_delete') }}
                </q-btn>
            </div>
        </q-card>

        <!-- QĐ3-6: switching off the last option of a required group -->
        <q-dialog v-model="showSoldOut">
            <q-card class="confirm-dialog">
                <q-card-section>
                    <div class="dialog-title">{{ $t('seller_menu.og_sold_out_title') }}</div>
                    <div class="dialog-sub">{{ $t('seller_menu.og_sold_out_body', { names: dishNames }) }}</div>
                </q-card-section>
                <q-card-actions align="right">
                    <q-btn flat no-caps :label="$t('common.button_label_cancel')" v-close-popup />
                    <q-btn flat no-caps color="warning" :loading="saving" @click="save(true)">{{ $t('seller_menu.og_sold_out_action') }}</q-btn>
                </q-card-actions>
            </q-card>
        </q-dialog>

        <q-dialog v-model="showDelete">
            <q-card class="confirm-dialog">
                <q-card-section>
                    <div class="dialog-title">{{ $t('seller_menu.og_delete_confirm_title') }}</div>
                    <div class="dialog-sub">{{ $t('seller_menu.og_delete_confirm_body') }}</div>
                </q-card-section>
                <q-card-actions align="right">
                    <q-btn flat no-caps :label="$t('common.button_label_cancel')" v-close-popup />
                    <q-btn flat no-caps color="negative" :loading="saving" @click="deleteGroup">{{ $t('seller_menu.og_delete') }}</q-btn>
                </q-card-actions>
            </q-card>
        </q-dialog>
    </q-dialog>
</template>

<style lang="scss" scoped>
.og-sheet {
    background: #1f2940;
    border-radius: 20px 20px 0 0;
    color: var(--text-primary);
    max-height: 90vh;
    display: flex;
    flex-direction: column;
}

.sheet-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 16px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}

.sheet-title { font-size: 17px; font-weight: 700; }

.btn-close {
    background: rgba(255,255,255,0.08);
    border: none;
    border-radius: 50%;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--text-secondary);
}

.sheet-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.sheet-footer {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 16px calc(12px + env(safe-area-inset-bottom, 0));
    border-top: 1px solid rgba(255,255,255,0.07);
}

.field-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-bottom: 6px;
}

.hint {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 6px;
    line-height: 1.4;
}

.hint--error { color: var(--negative, #e5484d); }

.question { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }

.radio-rows {
    background: rgba(255,255,255,0.04);
    border-radius: 10px;
}

/* every row the same height, so the number box showing does not move anything */
.radio-row {
    display: flex;
    align-items: center;
    width: 100%;
    min-height: 48px;
    padding: 0 8px 0 4px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    &:last-child { border-bottom: none; }
}

.radio-grow { flex: 1; min-height: 48px; }

.max-input { width: 72px; }

.option-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 8px;
}

.option-row {
    display: flex;
    align-items: center;
    gap: 8px;
}

.option-name { flex: 1; min-width: 0; }
.option-price { width: 104px; }

.btn-icon {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    width: 32px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    &:disabled { opacity: 0.3; cursor: default; }
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

.note {
    font-size: 12px;
    line-height: 1.4;
    color: var(--color-accent);
    background: var(--accent-dim, rgba(250,204,21,0.12));
    border-radius: 10px;
    padding: 10px 12px;
}

.btn-copy {
    display: block;
    margin-top: 8px;
    min-height: 36px;
    padding: 0 12px;
    background: none;
    border: 1px solid var(--color-accent);
    border-radius: 8px;
    color: var(--color-accent);
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
}

.btn-save {
    background: var(--color-accent);
    color: #121b2f;
    font-weight: 700;
    font-size: 14px;
    border-radius: 12px;
    padding: 12px;
}

.btn-danger { color: #ef4444; font-size: 14px; }

.confirm-dialog {
    background: #1f2940;
    border-radius: 16px;
    min-width: 280px;
    color: var(--text-primary);
}

.dialog-title { font-size: 17px; font-weight: 700; margin-bottom: 4px; }
.dialog-sub   { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }
</style>
