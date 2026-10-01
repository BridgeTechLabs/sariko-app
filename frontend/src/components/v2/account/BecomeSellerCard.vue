<script>
import { mapState } from 'pinia';
import { useAccountV2Store } from '@/stores/v2/account/accountStore';
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';
import BaseButton from '@/components/v2/shared/BaseButton.vue';

export default {
    components: { BaseIcon, BaseButton },

    computed: {
        ...mapState(useAccountV2Store, ['foundingSlotsLeft']),
    },
}
</script>

<template>
    <div class="seller-card">
        <div class="ellipse" />
        <div class="eyebrow">
            <BaseIcon name="store" :size="16" />
            <span>{{ $t('account_v2.become_seller_eyebrow') }}</span>
        </div>
        <p class="title">{{ $t('account_v2.become_seller_title') }}</p>
        <p class="desc">{{ $t('account_v2.become_seller_desc', { count: foundingSlotsLeft }) }}</p>
        <BaseButton variant="gold" :size="40" icon="arrow-right">
            {{ $t('account_v2.become_seller_cta') }}
        </BaseButton>
    </div>
</template>

<style scoped>
p {
    margin: 0;
}

.seller-card {
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-16);
    padding: var(--space-24);
    border-radius: var(--radius-xl);
    background: var(--brand-navy);
}

/* Keep content above the decorative ellipse */
.seller-card > :not(.ellipse) {
    position: relative;
}

.ellipse {
    position: absolute;
    top: -60px;
    right: -56px;
    width: 160px;
    height: 160px;
    border-radius: var(--radius-full);
    background: var(--brand-gold);
    opacity: 0.18;
}

.eyebrow {
    display: flex;
    align-items: center;
    gap: var(--space-8);
    color: var(--brand-gold-hi);
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-bold);
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.title {
    max-width: 300px;
    font-size: var(--font-size-base);
    line-height: var(--font-line-height-24);
    font-weight: var(--font-weight-semibold);
    color: var(--brand-navy-foreground);
}

.desc {
    max-width: 300px;
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--brand-navy-foreground-muted);
}
</style>
