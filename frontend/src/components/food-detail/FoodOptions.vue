<script>
import { mapActions, mapState } from 'pinia';
import { useSellerStore } from '@/stores/seller/sellerStore';
import { formatVnd } from '@/utils/priceDisplay';

// The dish's price levels and option groups (seller-menu đợt 3): radio for a required "choose 1", checkbox otherwise.
// Every row is one tappable label; an option the seller switched off stays visible as "Not available".
// The price levels are one more required "choose 1" group on top, each row with the level's full price (Jack 13/11);
// a level that is off stays hidden, as before.
export default {
    computed: {
        ...mapState(useSellerStore, ['currentFood', 'foodGroups', 'selectedOptionIds', 'selectedVariantId']),
        groups() {
            const levels = (this.currentFood?.food_item_variants || []).filter(v => v.is_available !== false)
            if (!levels.length) return this.foodGroups
            const levelGroup = { id: 'levels', isLevel: true, name: this.$t('food_detail_page.label_price_levels'),
                is_required: true, max_select: 1, menu_options: levels.map(v => ({ ...v, is_available: true })) }
            return [levelGroup, ...this.foodGroups]
        },
    },

    methods: {
        ...mapActions(useSellerStore, ['toggleOption']),
        checked(group, option) {
            return group.isLevel ? option.id === this.selectedVariantId : this.selectedOptionIds.includes(option.id)
        },
        pick(group, option) {
            if (group.isLevel) useSellerStore().selectedVariantId = option.id
            else this.toggleOption(group, option.id)
        },
        formatVnd,
        isRadio(group) {
            return group.is_required && group.max_select === 1
        },
        rule(group) {
            const need = this.$t(group.is_required ? 'food_detail_page.options_required' : 'food_detail_page.options_optional')
            const count = group.max_select === 1 ? this.$t('food_detail_page.options_choose_one') : this.$t('food_detail_page.options_up_to', { n: group.max_select })
            return `${need} · ${count}`
        },
        full(group, option) {
            const picked = group.menu_options.filter(o => this.selectedOptionIds.includes(o.id)).length
            return group.max_select > 1 && picked >= group.max_select && !this.selectedOptionIds.includes(option.id)
        }
    }
}
</script>

<template>
    <div v-if="groups.length" class="food-options">
        <fieldset v-for="group in groups" :key="group.id" class="group">
            <legend class="group-head">
                <span class="group-name">{{ group.name }}</span>
                <span class="group-rule" :class="{ 'group-rule--on': group.is_required }">{{ rule(group) }}</span>
            </legend>
            <label
                v-for="option in group.menu_options"
                :key="option.id"
                class="option"
                :class="{ 'option--off': !option.is_available }"
            >
                <input
                    :type="isRadio(group) ? 'radio' : 'checkbox'"
                    :name="group.id"
                    :checked="checked(group, option)"
                    :disabled="!option.is_available || full(group, option)"
                    @change="pick(group, option)"
                />
                <span class="option-name">
                    {{ option.name }}
                    <small v-if="!option.is_available">{{ $t('food_detail_page.option_not_available') }}</small>
                </span>
                <span class="option-price">{{ group.isLevel ? formatVnd(option.price) : '+' + formatVnd(option.extra_price) }}</span>
            </label>
        </fieldset>
    </div>
</template>

<style lang="scss" scoped>
.food-options {
    margin-top: 16px;
}

.group {
    border: 0;
    margin: 0;
    padding: 0 0 8px;
    min-width: 0;

    & + & {
        border-top: 6px solid rgba(255, 255, 255, 0.05);
        padding-top: 12px;
    }
}

.group-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 0;
    margin-bottom: 4px;
}

.group-name {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
}

.group-rule {
    flex-shrink: 0;
    padding: 2px 8px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: 600;

    &--on {
        background: rgba(245, 166, 35, 0.15);
        color: #f5A623;
    }
}

.option {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 48px;
    cursor: pointer;

    input {
        width: 20px;
        height: 20px;
        margin: 0;
        flex-shrink: 0;
        accent-color: #f5A623;
    }

    &--off {
        cursor: default;
        opacity: 0.45;
    }
}

.option-name {
    flex: 1;
    min-width: 0;
    font-size: 15px;
    color: var(--text-primary);

    small {
        display: block;
        font-size: 12px;
        color: var(--text-secondary);
    }
}

.option-price {
    font-size: 14px;
    color: var(--text-secondary);
    font-variant-numeric: tabular-nums;
}
</style>
