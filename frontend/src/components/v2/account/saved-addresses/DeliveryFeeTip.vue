<script>
import { mapState } from 'pinia';
import { useAccountV2Store } from '@/stores/v2/account/accountStore';
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';

export default {
    components: { BaseIcon },

    computed: {
        ...mapState(useAccountV2Store, ['deliveryFeeEstimate']),

        feeText() {
            return new Intl.NumberFormat('vi-VN').format(this.deliveryFeeEstimate) + ' ₫'
        },
    },
}
</script>

<template>
    <div class="tip">
        <BaseIcon class="icon" name="info" :size="16" />
        <p class="text">{{ $t('account_v2.addresses_fee_tip', { fee: feeText }) }}</p>
    </div>
</template>

<style scoped>
.tip {
    display: flex;
    align-items: center;
    gap: var(--space-16);
    padding: var(--space-16);
    border-radius: var(--radius-lg);
    background: var(--secondary);
}

.icon {
    color: var(--icon-muted);
}

.text {
    margin: 0;
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-secondary);
}
</style>
