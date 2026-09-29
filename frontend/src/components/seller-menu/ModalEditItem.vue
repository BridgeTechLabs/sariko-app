<script>
import { useMenuStore } from '@/stores/seller/menuStore'
import { ImagePlus, X, Plus, Trash2 } from 'lucide-vue-next'

export default {
    name: 'ModalEditItem',

    components: { ImagePlus, X, Plus, Trash2 },

    props: {
        modelValue: { type: Boolean, default: false },
        // null = create, object = edit
        item: { type: Object, default: null },
        // pre-select category when creating from a section
        defaultCategoryId: { type: String, default: null },
    },

    emits: ['update:modelValue'],

    data() {
        return {
            form: this._emptyForm(),
            imageFile: null,
            imagePreview: null,
            saving: false,
            deleting: false,
            showDeleteConfirm: false,
            uploadProgress: false,
        }
    },

    computed: {
        isEdit() { return !!this.item },
        canSave() {
            const variantsOk = this.form.variants.every(v => v.name.trim() && v.price > 0)
            return this.form.name.trim() && this.form.price > 0 && this.form.category_id && variantsOk && !this.saving
        },
        categoryOptions() {
            return useMenuStore().categories.map(c => ({ label: c.name, value: c.id }))
        },
    },

    watch: {
        modelValue(val) {
            if (val) this._resetForm()
        },
    },

    methods: {
        _emptyForm() {
            return {
                category_id: null,
                name: '',
                description: '',
                price: null,
                unit_label: '',
                min_quantity: 1,
                quantity_step: 1,
                preorder_day: 0,
                is_available: true,
                is_featured: false,
                image_url: null,
                variants: [],
            }
        },

        _resetForm() {
            this.imageFile = null
            this.imagePreview = null
            if (this.isEdit) {
                this.form = {
                    category_id: this.item.category_id || null,
                    name: this.item.name || '',
                    description: this.item.description || '',
                    price: this.item.price || null,
                    unit_label: this.item.unit_label || '',
                    min_quantity: this.item.min_quantity ?? 1,
                    quantity_step: this.item.quantity_step ?? 1,
                    preorder_day: this.item.preorder_day ?? 0,
                    is_available: this.item.is_available ?? true,
                    is_featured: this.item.is_featured ?? false,
                    image_url: this.item.image_url || null,
                    // Copied, not referenced: cancelling the modal must leave the
                    // store's rows untouched.
                    variants: (this.item.food_item_variants || []).map(v => ({
                        id: v.id,
                        name: v.name,
                        price: v.price,
                        is_available: v.is_available !== false,
                    })),
                }
            } else {
                this.form = this._emptyForm()
                this.form.category_id = this.defaultCategoryId || null
            }
        },

        close() { this.$emit('update:modelValue', false) },

        addVariant() {
            this.form.variants.push({ id: null, name: '', price: null, is_available: true })
        },

        removeVariant(idx) {
            this.form.variants.splice(idx, 1)
        },

        onImagePick(e) {
            const file = e.target.files?.[0]
            if (!file) return
            this.imageFile = file
            this.imagePreview = URL.createObjectURL(file)
        },

        removeImage() {
            this.imageFile = null
            this.imagePreview = null
            this.form.image_url = null
        },

        async save() {
            if (!this.canSave) return
            this.saving = true
            try {
                const store = useMenuStore()
                const payload = {
                    category_id: this.form.category_id || undefined,
                    name: this.form.name.trim(),
                    description: this.form.description?.trim() || undefined,
                    price: Number(this.form.price),
                    unit_label: this.form.unit_label?.trim() || undefined,
                    min_quantity: this.form.min_quantity,
                    quantity_step: this.form.quantity_step,
                    preorder_day: this.form.preorder_day,
                    is_available: this.form.is_available,
                    is_featured: this.form.is_featured,
                }

                // Clear image explicitly if removed
                if (!this.form.image_url && !this.imageFile && this.isEdit && this.item.image_url) {
                    payload.image_url = null
                }

                let itemId
                if (this.isEdit) {
                    const updated = await store.updateItem(this.item.id, payload)
                    itemId = updated.id
                } else {
                    const created = await store.createItem(payload)
                    itemId = created.id
                }

                // Levels need the item ID too, so they go after create/update.
                await store.syncVariants(itemId, this.form.variants)

                // Upload image after we have the item ID
                if (this.imageFile) {
                    this.uploadProgress = true
                    const publicUrl = await store.uploadImage(itemId, this.imageFile)
                    await store.updateItem(itemId, { image_url: publicUrl })
                }

                this.$q.notify({ classes: 'quasar-notify-positive', message: this.$t('seller_menu.toast_item_saved'), position: 'bottom', timeout: 1500 })
                this.close()
            } catch (e) {
                console.error('ModalEditItem - save -', e)
                this.$q.notify({ type: 'negative', message: this.$t('seller_menu.toast_save_failed'), position: 'bottom' })
            } finally {
                this.saving = false
                this.uploadProgress = false
            }
        },

        async confirmDelete() {
            this.deleting = true
            try {
                await useMenuStore().deleteItem(this.item.id)
                this.showDeleteConfirm = false
                this.close()
                this.$q.notify({ classes: 'quasar-notify-positive', message: this.$t('seller_menu.toast_item_deleted'), position: 'bottom', timeout: 1500 })
            } catch (e) {
                console.error('ModalEditItem - confirmDelete -', e)
                this.$q.notify({ type: 'negative', message: this.$t('seller_menu.toast_delete_failed'), position: 'bottom' })
            } finally {
                this.deleting = false
            }
        },
    },
}
</script>

<template>
    <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" position="bottom" full-width>
        <q-card class="item-sheet">

            <!-- Header -->
            <div class="sheet-header">
                <span class="sheet-title">
                    {{ isEdit ? $t('seller_menu.item_edit_title') : $t('seller_menu.item_add_title') }}
                </span>
                <button class="btn-close" @click="close"><X :size="20" /></button>
            </div>

            <div class="sheet-body">

                <!-- Image picker -->
                <div class="image-section">
                    <div v-if="imagePreview || form.image_url" class="image-preview-wrap">
                        <img :src="imagePreview || form.image_url" class="image-preview" />
                        <button class="btn-remove-img" @click="removeImage"><X :size="14" /></button>
                    </div>
                    <label v-else class="image-placeholder">
                        <ImagePlus :size="28" style="color:var(--text-muted);" />
                        <span class="image-hint">{{ $t('seller_menu.image_pick') }}</span>
                        <input type="file" accept="image/*" class="file-input" @change="onImagePick" />
                    </label>
                </div>

                <!-- Category -->
                <div class="field-group">
                    <div class="field-label">{{ $t('seller_menu.item_category') }}</div>
                    <q-select
                        v-model="form.category_id"
                        :options="categoryOptions"
                        emit-value map-options
                        dense outlined dark
                        :placeholder="$t('seller_menu.item_category_placeholder')"
                        clearable
                        popup-content-class="dark-popup"
                    />
                </div>

                <!-- Name -->
                <div class="field-group">
                    <div class="field-label">{{ $t('seller_menu.item_name') }} *</div>
                    <q-input v-model="form.name" dense outlined dark :placeholder="$t('seller_menu.item_name_placeholder')" />
                </div>

                <!-- Description -->
                <div class="field-group">
                    <div class="field-label">{{ $t('seller_menu.item_description') }}</div>
                    <q-input v-model="form.description" dense outlined dark type="textarea" rows="2" :placeholder="$t('seller_menu.item_description_placeholder')" />
                </div>

                <!-- Price + Unit label -->
                <div class="field-row">
                    <div class="field-group flex-1">
                        <div class="field-label">{{ $t('seller_menu.item_price') }} * (₫)</div>
                        <q-input v-model.number="form.price" dense outlined dark type="number" :placeholder="$t('seller_menu.item_price_placeholder')" />
                    </div>
                    <div class="field-group" style="width:110px;">
                        <div class="field-label">{{ $t('seller_menu.item_unit_label') }}</div>
                        <q-input v-model="form.unit_label" dense outlined dark :placeholder="$t('seller_menu.item_unit_label_placeholder')" />
                    </div>
                </div>

                <!-- Price levels (S/M/L, 1-2-4 people, …) -->
                <div class="field-group">
                    <div class="field-label">{{ $t('seller_menu.variants_label') }}</div>
                    <div v-if="form.variants.length" class="variant-list">
                        <div v-for="(v, idx) in form.variants" :key="idx" class="variant-row">
                            <q-input v-model="v.name" dense outlined dark class="variant-name"
                                :placeholder="$t('seller_menu.variant_name_placeholder')" />
                            <q-input v-model.number="v.price" dense outlined dark type="number" class="variant-price"
                                :placeholder="$t('seller_menu.variant_price_placeholder')" />
                            <q-toggle v-model="v.is_available" dense color="amber" />
                            <button class="btn-variant-remove" @click="removeVariant(idx)">
                                <Trash2 :size="16" />
                            </button>
                        </div>
                    </div>
                    <button class="btn-variant-add" @click="addVariant">
                        <Plus :size="16" /> {{ $t('seller_menu.variant_add') }}
                    </button>
                    <div class="variant-hint">
                        {{ form.variants.length ? $t('seller_menu.variants_hint_active') : $t('seller_menu.variants_hint_empty') }}
                    </div>
                </div>

                <!-- Min qty + Step + Preorder -->
                <div class="field-row">
                    <div class="field-group flex-1">
                        <div class="field-label">{{ $t('seller_menu.item_min_quantity') }}</div>
                        <q-input v-model.number="form.min_quantity" dense outlined dark type="number" :min="1" />
                    </div>
                    <div class="field-group flex-1">
                        <div class="field-label">{{ $t('seller_menu.item_quantity_step') }}</div>
                        <q-input v-model.number="form.quantity_step" dense outlined dark type="number" :min="1" />
                    </div>
                    <div class="field-group flex-1">
                        <div class="field-label">{{ $t('seller_menu.item_preorder_day') }}</div>
                        <q-input v-model.number="form.preorder_day" dense outlined dark type="number" :min="0" />
                    </div>
                </div>

                <!-- Toggles -->
                <div class="toggle-row">
                    <div class="toggle-item">
                        <span class="toggle-label">{{ $t('seller_menu.item_available') }}</span>
                        <q-toggle v-model="form.is_available" color="positive" />
                    </div>
                    <div class="toggle-item">
                        <span class="toggle-label">{{ $t('seller_menu.item_featured') }}</span>
                        <q-toggle v-model="form.is_featured" color="warning" />
                    </div>
                </div>

            </div>

            <!-- Actions -->
            <div class="sheet-footer">
                <q-btn
                    v-if="isEdit"
                    flat no-caps class="btn-delete"
                    :loading="deleting"
                    @click="showDeleteConfirm = true"
                >
                    {{ $t('seller_menu.item_delete') }}
                </q-btn>
                <div style="flex:1" />
                <q-btn unelevated no-caps class="btn-save" :disable="!canSave" :loading="saving" @click="save">
                    {{ uploadProgress ? $t('seller_menu.uploading') : $t('common.button_label_save') }}
                </q-btn>
            </div>

        </q-card>

        <!-- Delete confirm -->
        <q-dialog v-model="showDeleteConfirm">
            <q-card class="confirm-dialog">
                <q-card-section>
                    <div class="dialog-title">{{ $t('seller_menu.item_delete_confirm_title') }}</div>
                    <div class="dialog-sub">{{ $t('seller_menu.item_delete_confirm_body') }}</div>
                </q-card-section>
                <q-card-actions align="right">
                    <q-btn flat no-caps :label="$t('common.button_label_cancel')" v-close-popup />
                    <q-btn flat no-caps color="negative" :loading="deleting" @click="confirmDelete">
                        {{ $t('seller_menu.item_delete_confirm_action') }}
                    </q-btn>
                </q-card-actions>
            </q-card>
        </q-dialog>
    </q-dialog>
</template>

<style lang="scss" scoped>
.item-sheet {
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
    flex-shrink: 0;
}

.sheet-title {
    font-size: 17px;
    font-weight: 700;
}

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
    gap: 14px;
}

.sheet-footer {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px calc(12px + env(safe-area-inset-bottom, 0));
    border-top: 1px solid rgba(255,255,255,0.07);
    flex-shrink: 0;
}

/* Image */
.image-section { display: flex; justify-content: center; }

.image-placeholder {
    width: 100%;
    height: 140px;
    border: 2px dashed rgba(255,255,255,0.15);
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    cursor: pointer;
}

.image-hint { font-size: 13px; color: var(--text-muted); }

.file-input { display: none; }

.image-preview-wrap {
    position: relative;
    width: 100%;
    height: 160px;
    border-radius: 12px;
    overflow: hidden;
}

.image-preview {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.btn-remove-img {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 26px;
    height: 26px;
    background: rgba(0,0,0,0.6);
    border: none;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: #fff;
}

/* Fields */
.field-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-bottom: 6px;
}

.field-row {
    display: flex;
    gap: 10px;
}

.variant-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 8px;
}

.variant-row {
    display: flex;
    align-items: center;
    gap: 8px;
}

.variant-name { flex: 1; }
.variant-price { width: 120px; }

.btn-variant-remove {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px;
    display: flex;
    &:hover { color: #ef4444; }
}

.btn-variant-add {
    display: flex;
    align-items: center;
    gap: 6px;
    background: none;
    border: 1px dashed rgba(255,255,255,0.2);
    border-radius: 10px;
    color: var(--text-muted);
    font-size: 13px;
    padding: 8px 12px;
    width: 100%;
    justify-content: center;
    cursor: pointer;
    &:hover { color: var(--accent, #f5A623); border-color: var(--accent, #f5A623); }
}

.variant-hint {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 6px;
    line-height: 1.4;
}

.flex-1 { flex: 1; }

.toggle-row {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.toggle-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    &:last-child { border-bottom: none; }
}

.toggle-label {
    font-size: 14px;
    color: var(--text-primary);
}

/* Actions */
.btn-save {
    background: var(--color-accent);
    color: #121b2f;
    font-weight: 700;
    font-size: 14px;
    border-radius: 12px;
    padding: 10px 24px;
}

.btn-delete {
    color: #ef4444;
    font-size: 13px;
}

/* Confirm dialog */
.confirm-dialog {
    background: #1f2940;
    border-radius: 16px;
    min-width: 280px;
    color: var(--text-primary);
}

.dialog-title { font-size: 17px; font-weight: 700; margin-bottom: 4px; }
.dialog-sub   { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }

:deep(.dark-popup) {
    background: #1f2940;
    color: var(--text-primary);
}
</style>
