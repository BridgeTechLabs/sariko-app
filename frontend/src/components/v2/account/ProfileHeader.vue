<script>
import { mapState, mapActions } from 'pinia';
import { useAccountV2Store } from '@/stores/v2/account/accountStore';
import BaseAvatar from '@/components/v2/shared/BaseAvatar.vue';
import BaseIconButton from '@/components/v2/shared/BaseIconButton.vue';

export default {
    components: { BaseAvatar, BaseIconButton },

    computed: {
        ...mapState(useAccountV2Store, ['profile', 'stats', 'initials']),

        metaText() {
            return [this.profile.phone, this.profile.district].filter(Boolean).join(' · ')
        },

        statCells() {
            return [
                { value: this.stats.orders, label: this.$t('account_v2.stat_orders') },
                { value: this.stats.reviews, label: this.$t('account_v2.stat_reviews') },
                { value: this.stats.following, label: this.$t('account_v2.stat_following') },
            ]
        },
    },

    mounted() {
        this.fetchAccount()
    },

    methods: {
        ...mapActions(useAccountV2Store, ['fetchAccount']),
    },
}
</script>

<template>
    <div class="header-wrap">
        <div class="header">
            <div class="profile">
                <BaseAvatar :src="profile.avatarUrl || null" :initials="initials" :size="64" />
                <div class="info">
                    <p class="name">{{ profile.name }}</p>
                    <p class="meta">{{ metaText }}</p>
                </div>
                <BaseIconButton
                    icon="pencil"
                    surface="photo"
                    :label="$t('account_v2.edit_profile')"
                    @click="$router.push({ name: 'account-edit-profile-v2' })"
                />
            </div>
        </div>

        <div class="stats">
            <template v-for="(cell, i) in statCells" :key="cell.label">
                <div v-if="i > 0" class="sep" />
                <div class="cell">
                    <p class="value">{{ cell.value }}</p>
                    <p class="label">{{ cell.label }}</p>
                </div>
            </template>
        </div>
    </div>
</template>

<style scoped>
p {
    margin: 0;
}

.header {
    background: var(--brand-navy);
    border-radius: 0 0 var(--radius-2xl) var(--radius-2xl);
    padding: max(var(--space-56), calc(env(safe-area-inset-top, 0px) + 12px)) var(--space-24) var(--space-80);
}

.profile {
    display: flex;
    align-items: center;
    gap: var(--space-16);
}

.info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-8);
}

.name {
    font-size: var(--font-size-lg);
    line-height: var(--font-line-height-24);
    font-weight: var(--font-weight-semibold);
    letter-spacing: -0.005em;
    color: var(--brand-navy-foreground);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.meta {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--brand-navy-foreground-muted);
}

.stats {
    position: relative;
    /* Overlaps the bottom of the navy header */
    margin: -44px var(--space-24) 0;
    height: 72px;
    padding: var(--space-16) var(--space-8);
    background: var(--card);
    border-radius: var(--radius-xl);
    box-shadow: 0 8px 24px -6px color-mix(in srgb, var(--brand-navy) 10%, transparent);
    display: flex;
    align-items: center;
}

.cell {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-8);
}

.value {
    font-size: var(--font-size-base);
    line-height: var(--font-line-height-24);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.label {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-secondary);
}

.sep {
    width: var(--border-default);
    height: 32px;
    background: var(--divider);
}
</style>
