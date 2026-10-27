<script>
import { mapState, mapWritableState, mapActions } from 'pinia'
import { AlertTriangle, ChevronRight, ChevronDown, ChevronUp } from 'lucide-vue-next'
import { useProfileCompletionStore } from '@/stores/seller/profileCompletionStore'

// Reminder only: selling is never blocked (spec seller-profile-completion D4 / Q3).
export default {
    name: 'ProfileCompletionBanner',

    components: { AlertTriangle, ChevronRight, ChevronDown, ChevronUp },

    computed: {
        ...mapState(useProfileCompletionStore, ['missing', 'data']),
        ...mapWritableState(useProfileCompletionStore, ['bannerCollapsed']),
        missingText() {
            return this.missing.map(g => this.$t(`seller_profile.group_${g}`)).join(', ')
        },
    },

    methods: {
        ...mapActions(useProfileCompletionStore, ['fetch']),
    },

    mounted() {
        this.fetch()
    },
}
</script>

<template>
    <div v-if="data && missing.length" class="profile-banner">
        <div class="banner-head">
            <AlertTriangle :size="18" class="banner-icon" />
            <div class="banner-title">{{ $t('seller_profile.banner_title') }}</div>
            <button class="banner-toggle" :aria-label="$t('seller_profile.banner_toggle')" @click="bannerCollapsed = !bannerCollapsed">
                <ChevronDown v-if="bannerCollapsed" :size="18" />
                <ChevronUp v-else :size="18" />
            </button>
        </div>
        <template v-if="!bannerCollapsed">
            <div class="banner-text">{{ $t('seller_profile.banner_missing', { items: missingText }) }}</div>
            <router-link to="/seller/me/profile" class="banner-link">
                {{ $t('seller_profile.banner_action') }} <ChevronRight :size="16" />
            </router-link>
        </template>
    </div>
</template>

<style scoped>
.profile-banner {
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid var(--color-warning);
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 12px;
    color: var(--text-primary);
}

.banner-head {
    display: flex;
    align-items: center;
    gap: 8px;
}

.banner-icon {
    color: var(--color-warning);
    flex-shrink: 0;
}

.banner-title {
    flex: 1;
    font-size: 14px;
    font-weight: 600;
}

.banner-toggle {
    background: none;
    border: none;
    color: var(--text-secondary);
    padding: 4px;
    cursor: pointer;
    display: flex;
}

.banner-text {
    font-size: 13px;
    color: var(--text-secondary);
    margin: 6px 0 8px 26px;
}

.banner-link {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    margin-left: 26px;
    font-size: 14px;
    font-weight: 600;
    color: var(--color-warning);
    text-decoration: none;
}
</style>
