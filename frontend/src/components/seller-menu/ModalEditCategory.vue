<script>
import { useMenuStore } from '@/stores/seller/menuStore'
import { X, ArrowUp, ArrowDown } from 'lucide-vue-next'

export default {
    name: 'ModalEditCategory',

    components: { X, ArrowUp, ArrowDown },

    props: {
        modelValue: { type: Boolean, default: false },
        // null = create mode, object = edit mode
        category: { type: Object, default: null },
    },

    emits: ['update:modelValue', 'saved'],

    data() {
        return {
            name: '',
            saving: false,
            moving: false,
        }
    },

    computed: {
        isEdit()    { return !!this.category },
        canSave()   { return this.name.trim().length > 0 && !this.saving },
        position()  { return useMenuStore().categories.findIndex(c => c.id === this.category?.id) },
        isFirst()   { return this.position <= 0 },
        isLast()    { return this.position === useMenuStore().categories.length - 1 },
    },

    watch: {
        modelValue(val) {
            if (val) this.name = this.category?.name || ''
        },
    },

    methods: {
        close() { this.$emit('update:modelValue', false) },

        // Saved at once, not with the Save button
        async move(step) {
            if (this.moving) return
            this.moving = true
            try {
                await useMenuStore().moveCategory(this.category.id, step)
            } catch (e) {
                console.error('ModalEditCategory - move -', e)
                this.$q.notify({ type: 'negative', message: this.$t('seller_menu.category_move_failed'), position: 'bottom' })
            } finally {
                this.moving = false
            }
        },

        async save() {
            if (!this.canSave) return
            this.saving = true
            try {
                const store = useMenuStore()
                if (this.isEdit) {
                    await store.updateCategory(this.category.id, { name: this.name.trim() })
                } else {
                    this.$emit('saved', await store.createCategory(this.name.trim()))
                }
                this.close()
            } catch (e) {
                console.error('ModalEditCategory - save -', e)
                this.$q.notify({ type: 'negative', message: this.$t('seller_menu.toast_save_failed'), position: 'bottom' })
            } finally {
                this.saving = false
            }
        },

    },
}
</script>

<template>
    <q-dialog :model-value="modelValue" position="bottom" full-width @update:model-value="$emit('update:modelValue', $event)">
        <q-card class="edit-sheet">
            <div class="sheet-header">
                <span class="sheet-title">
                    {{ isEdit ? $t('seller_menu.category_edit_title') : $t('seller_menu.category_add_title') }}
                </span>
                <button class="btn-close" @click="close"><X :size="20" /></button>
            </div>

            <div class="sheet-body">
                <div>
                    <div class="field-label">{{ $t('seller_menu.category_name_label') }}</div>
                    <q-input
                        v-model="name"
                        dense outlined dark autofocus
                        :placeholder="$t('seller_menu.category_name_placeholder')"
                        @keyup.enter="save"
                    />
                    <div v-if="!isEdit" class="field-hint">{{ $t('seller_menu.category_name_hint') }}</div>
                </div>

                <div v-if="isEdit">
                    <div class="field-label">{{ $t('seller_menu.category_position') }}</div>
                    <div class="move-row">
                        <button class="btn-move" :disabled="isFirst || moving" @click="move(-1)">
                            <ArrowUp :size="16" /> {{ $t('seller_menu.category_move_up') }}
                        </button>
                        <button class="btn-move" :disabled="isLast || moving" @click="move(1)">
                            <ArrowDown :size="16" /> {{ $t('seller_menu.category_move_down') }}
                        </button>
                    </div>
                </div>
            </div>

            <div class="sheet-footer">
                <q-btn unelevated no-caps class="btn-save" :disable="!canSave" :loading="saving" @click="save">
                    {{ $t('common.button_label_save') }}
                </q-btn>
            </div>
        </q-card>
    </q-dialog>
</template>

<style lang="scss" scoped>
.edit-sheet {
    background: #1f2940;
    border-radius: 20px 20px 0 0;
    color: var(--text-primary);
    padding-bottom: env(safe-area-inset-bottom, 0);
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
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.field-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin-bottom: 6px;
}

.field-hint {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 6px;
}

.move-row { display: flex; gap: 10px; }

.btn-move {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px;
    border: none;
    border-radius: 10px;
    background: rgba(255,255,255,0.07);
    color: var(--text-secondary);
    font-size: 14px;
    font-family: inherit;
    cursor: pointer;
    &:disabled { opacity: 0.4; cursor: default; }
}

.sheet-footer {
    padding: 12px 16px;
    border-top: 1px solid rgba(255,255,255,0.07);
}

.btn-save {
    width: 100%;
    background: var(--color-accent);
    color: #121b2f;
    font-weight: 700;
    font-size: 15px;
    border-radius: 12px;
    padding: 12px;
}


</style>
