<script>
import { MessageSquare } from 'lucide-vue-next';
import { mapWritableState } from 'pinia';
import { useCartStore } from '@/stores/cart/cartStore';

export default {
    components: {
        MessageSquare
    },

    computed: {
        ...mapWritableState(useCartStore, ['note'])
    }
}
</script>

<template>
    <div class="note-container">
        <div class="title">
            <MessageSquare :size="16" class="icon" />
            {{ $t('cart_page.note_label') }}
        </div>
        <div class="note-field">
            <q-input
            v-model="note"
            dense
            dark
            type="textarea"
            rows="2"
            :placeholder="$t('cart_page.note_placeholder')"
            class="note"
        />
        </div>
    </div>
</template>

<style lang="scss">

.note-container {
    border: 1px solid var(--border-color);
    border-radius: 1rem;
    padding: 10px 15px;
    font-family: $sariko-font-family-secondary;
    background: rgba(255, 255, 255, 0.05);
}

.title {
    display: flex;
    align-items: center;
    font-size: 14px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.55);
    margin-bottom: 8px;
}

.icon {
    margin-right: 8px;
}

.note-fields {
    width: 100%;

    :deep(.q-field__control) {
        border-radius: .75rem;
        // background-color: var(--bg-surface);
    }

    :deep(.q-field__native) {
        color: white;
        font-size: 14px;
        resize: none;

        &::placeholder {
            color: rgba(255, 255, 255, 0.3);
        }
    }
}
</style>
