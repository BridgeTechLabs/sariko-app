<script>
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';
import BasePill from '@/components/v2/shared/BasePill.vue';

const LABEL_ICONS = { home: 'home', work: 'store', other: 'map-pin' }

export default {
    components: { BaseIcon, BasePill },

    props: {
        address: {
            type: Object,
            required: true,
        },
    },

    computed: {
        labelIcon() {
            return LABEL_ICONS[this.address.label] || 'map-pin'
        },
    },
}
</script>

<template>
    <div class="address-card" :class="{ default: address.isDefault }">
        <div class="head">
            <div class="icon-box">
                <BaseIcon :name="labelIcon" :size="20" />
            </div>
            <div class="info">
                <div class="label-row">
                    <span class="label">{{ $t(`account_v2.address_label_${address.label}`) }}</span>
                    <BasePill v-if="address.isDefault">{{ $t('account_v2.address_default') }}</BasePill>
                </div>
                <p class="contact">{{ address.receiverName }} · {{ address.phone }}</p>
            </div>
            <button
                class="edit-btn"
                type="button"
                :aria-label="$t('account_v2.address_edit')"
                @click="$router.push({ name: 'account-address-edit-v2', params: { id: address.id } })"
            >
                <BaseIcon name="pencil" :size="18" />
            </button>
        </div>
        <p class="address">{{ address.address }}</p>
    </div>
</template>

<style scoped>
p {
    margin: 0;
}

.address-card {
    display: flex;
    flex-direction: column;
    gap: var(--space-16);
    padding: var(--space-16);
    background: var(--card);
    border-radius: var(--radius-xl);
    box-shadow: 0 2px 8px color-mix(in srgb, var(--brand-navy) 5%, transparent);
}

.address-card.default {
    border: var(--border-strong) solid var(--primary);
}

.head {
    display: flex;
    align-items: center;
    gap: var(--space-16);
}

.icon-box {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border-radius: var(--radius-full);
    background: var(--secondary);
    color: var(--icon-default);
    display: flex;
    align-items: center;
    justify-content: center;
}

.default .icon-box {
    background: var(--brand-gold-soft);
    color: var(--brand-gold);
}

.info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-8);
}

.label-row {
    display: flex;
    align-items: center;
    gap: var(--space-8);
}

.label {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.contact {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.edit-btn {
    flex-shrink: 0;
    padding: 0;
    border: none;
    background: none;
    color: var(--icon-muted);
    display: flex;
    cursor: pointer;
}

.address {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-primary);
}
</style>
