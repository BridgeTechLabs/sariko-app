<script>
import BaseIconButton from '@/components/v2/shared/BaseIconButton.vue';

export default {
    components: { BaseIconButton },
}
</script>

<template>
    <div class="top-bar">
        <BaseIconButton
            icon="arrow-left"
            :label="$t('account_v2.back')"
            @click="$router.push({ name: 'account-v2' })"
        />
        <div class="titles">
            <p class="title">{{ $t('account_v2.addresses_title') }}</p>
            <p class="sub">{{ $t('account_v2.addresses_subtitle') }}</p>
        </div>
    </div>
</template>

<style scoped>
p {
    margin: 0;
}

.top-bar {
    display: flex;
    align-items: center;
    gap: var(--space-16);
    padding: max(var(--space-48), calc(env(safe-area-inset-top, 0px) + 12px)) var(--space-24) var(--space-16);
}

.titles {
    flex: 1;
    min-width: 0;
}

.title {
    font-size: var(--font-size-lg);
    line-height: var(--font-line-height-24);
    font-weight: var(--font-weight-semibold);
    letter-spacing: -0.005em;
    color: var(--text-primary);
}

.sub {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-secondary);
}
</style>
