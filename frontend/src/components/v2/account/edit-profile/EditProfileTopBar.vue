<script>
import BaseIconButton from '@/components/v2/shared/BaseIconButton.vue';
import BaseSectionHead from '@/components/v2/shared/BaseSectionHead.vue';

export default {
    components: { BaseIconButton, BaseSectionHead },
}
</script>

<template>
    <div class="top-bar">
        <BaseIconButton
            icon="arrow-left"
            :label="$t('account_v2.back')"
            @click="$router.push({ name: 'account-v2' })"
        />
        <BaseSectionHead class="title" :title="$t('account_v2.edit_profile')" />
    </div>
</template>

<style scoped>
.top-bar {
    display: flex;
    align-items: center;
    gap: var(--space-16);
    padding: max(var(--space-48), calc(env(safe-area-inset-top, 0px) + 12px)) var(--space-24) var(--space-16);
}

.title {
    flex: 1;
    min-width: 0;
}
</style>
