<script>
import { mapState } from 'pinia'
import { AlertTriangle, ChevronRight } from 'lucide-vue-next'
import { useAuthStore, BUYER_MISSING_ROUTES } from '@/stores/auth/authStore.js'

// Tells a signed-in buyer early what blocks Place order in the cart (same list: authStore.buyerMissing).
export default {
    name: 'BuyerMissingBanner',

    components: { AlertTriangle, ChevronRight },

    computed: {
        ...mapState(useAuthStore, ['user', 'buyerInfoLoaded', 'buyerMissing']),
        show() {
            return !!this.user && !this.user.isSeller && this.buyerInfoLoaded && this.buyerMissing.length > 0
        },
    },

    methods: {
        routeOf(key) {
            return BUYER_MISSING_ROUTES[key]
        },
    },
}
</script>

<template>
    <div v-if="show" class="missing-banner">
        <div class="banner-head">
            <AlertTriangle :size="18" class="banner-icon" />
            <div class="banner-title">{{ $t('home_page.missing_banner.title') }}</div>
        </div>
        <div v-for="key in buyerMissing" :key="key" class="banner-row">
            <span class="banner-item">{{ $t(`home_page.missing_banner.${key}`) }}</span>
            <router-link :to="routeOf(key)" class="banner-link">
                {{ $t('home_page.missing_banner.action') }} <ChevronRight :size="16" />
            </router-link>
        </div>
    </div>
</template>

<style scoped>
.missing-banner {
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid var(--color-warning);
    border-radius: 12px;
    padding: 10px 14px;
    margin: 12px 0;
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
    font-size: 14px;
    font-weight: 600;
}

.banner-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin: 4px 0 0 26px;
}

.banner-item {
    font-size: 13px;
    color: var(--text-secondary);
    min-width: 0;
}

.banner-link {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    flex-shrink: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--color-warning);
    text-decoration: none;
}
</style>
