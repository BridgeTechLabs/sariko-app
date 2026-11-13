<script>
import { useMenuStore } from '@/stores/seller/menuStore'
import ModalEditItem from './ModalEditItem.vue'
import { foodPriceDisplay, hasVariants } from '@/utils/priceDisplay';
import { dayMonth } from '@/utils/portions';

export default {
    name: 'SellerMenuFoodItem',

    components: { ModalEditItem },

    props: {
        item: { type: Object, required: true },
    },

    data() {
        return {
            showEditModal: false,
            toggling: false,
        }
    },

    methods: {
        foodPriceDisplay, hasVariants, dayMonth,
        async onToggleAvailable(val) {
            this.toggling = true
            try {
                await useMenuStore().toggleAvailable(this.item.id, val)
            } catch (e) {
                console.error('SellerMenuFoodItem - onToggleAvailable -', e)
                this.$q.notify({ type: 'negative', message: this.$t('seller_menu.toast_save_failed'), position: 'bottom' })
            } finally {
                this.toggling = false
            }
        },
    },
}
</script>

<template>
    <div class="food-card" :class="{ off: !item.is_available }" @click="showEditModal = true">
        <img
            :src="item.image_url || '/images/default-food-image.webp'"
            class="food-thumb"
            @error="$event.target.src = '/images/default-food-image.webp'"
        />
        <div class="food-info">
            <div class="food-name">{{ item.name }}</div>
            <div class="food-sub">
                <span class="food-price">{{ foodPriceDisplay(item) }}</span>
                <template v-if="item.unit_label && !hasVariants(item)"> / {{ item.unit_label }}</template>
                <span v-if="!item.is_available" class="food-tag-off">{{ $t('seller_menu.item_off') }}</span>
                <!-- a required option group with every option off (QĐ3-6) -->
                <span v-else-if="item.options_sold_out" class="food-tag-off">{{ $t('seller_menu.item_options_sold_out') }}</span>
            </div>
            <div v-if="item.daily_portions" class="food-portions" :class="{ 'food-portions--out': (item.portions_date ? item.remaining_preorder : item.remaining_today) === 0 }">
                <!-- a pre-order dish counts its first delivery day, not today (T181 A34) -->
                <template v-if="item.portions_date">{{ $t('seller_menu.portions_left_on', { left: item.remaining_preorder, total: item.daily_portions, date: dayMonth(item.portions_date) }) }}</template>
                <template v-else>{{ $t('seller_menu.portions_left_today', { left: item.remaining_today ?? item.daily_portions, total: item.daily_portions }) }}</template>
            </div>
        </div>
        <q-toggle
            :model-value="item.is_available"
            color="positive"
            dense
            :disable="toggling"
            @click.stop
            @update:model-value="onToggleAvailable"
        />

        <ModalEditItem
            v-model="showEditModal"
            :item="item"
        />
    </div>
</template>

<style lang="scss" scoped>
.food-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    margin-bottom: 14px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    cursor: pointer;
    &.off .food-thumb { opacity: 0.4; }
    &.off .food-name { color: var(--text-muted); }
}

.food-thumb {
    width: 72px;
    height: 72px;
    border-radius: 12px;
    object-fit: cover;
    flex-shrink: 0;
    background: rgba(255,255,255,0.05);
}

.food-info {
    flex: 1;
    min-width: 0;
}

.food-name {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.food-sub {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 4px;
}

.food-price {
    color: var(--color-accent);
    font-weight: 600;
}

.food-tag-off {
    display: inline-block;
    margin-left: 6px;
    padding: 0 7px;
    font-size: 11px;
    line-height: 18px;
    color: var(--text-muted);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 6px;
}

.food-portions {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 3px;
    &--out { color: var(--color-error); }
}
</style>
