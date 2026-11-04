<script>
import { House, ClipboardList, UtensilsCrossed, CircleUserRound, Inbox } from 'lucide-vue-next';
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import { useChatStore } from '@/stores/chat/chatStore';

export default {
    name: 'SellerBottomNav',

    components: { House, ClipboardList, UtensilsCrossed, CircleUserRound, Inbox },

    computed: {
        isShow() {
            return this.$route.name !== 'seller-order-detail'
        },
        actionBadge() {
            return useDashboardStore().actionDisplayCount
        },
        chatBadge() {
            return useChatStore().totalUnread
        },
    },

    methods: {
        isActive(path) {
            return this.$route.path === path || this.$route.path.startsWith(path + '/')
        }
    },

    mounted() {
        const height = this.$refs.navRef?.offsetHeight || 0
        document.documentElement.style.setProperty('--bottom-nav-height', `${height}px`)
    }
}
</script>

<template>
    <nav ref="navRef" v-show="isShow" class="bottom-nav">
        <router-link to="/seller/home" class="nav-item" :class="{ active: isActive('/seller/home') }">
            <div class="icon-wrapper">
                <House size="18px" />
                <span v-if="actionBadge > 0" class="action-badge">{{ actionBadge }}</span>
            </div>
            <div class="nav-label">{{ $t('bottom_nav.button_label_today') }}</div>
        </router-link>

        <router-link to="/seller/orders" class="nav-item" :class="{ active: isActive('/seller/orders') }">
            <ClipboardList size="18px" />
            <div class="nav-label">{{ $t('bottom_nav.button_label_orders') }}</div>
        </router-link>

        <router-link to="/seller/menu" class="nav-item" :class="{ active: isActive('/seller/menu') }">
            <UtensilsCrossed size="18px" />
            <div class="nav-label">{{ $t('bottom_nav.button_label_menu') }}</div>
        </router-link>

        <router-link to="/chat" class="nav-item" :class="{ active: isActive('/chat') }">
            <div class="icon-wrapper">
                <Inbox size="18px" />
                <span v-if="chatBadge > 0" class="action-badge">{{ chatBadge }}</span>
            </div>
            <div class="nav-label">{{ $t('bottom_nav.button_label_inbox') }}</div>
        </router-link>

        <router-link to="/seller/me" class="nav-item" :class="{ active: isActive('/seller/me') }">
            <CircleUserRound size="18px" />
            <div class="nav-label">{{ $t('bottom_nav.button_label_me') }}</div>
        </router-link>
    </nav>
</template>

<style scoped>
.bottom-nav {
    max-width: 800px;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--bg-main);
    display: flex;
    margin: auto;
    justify-content: space-around;
    align-items: center;
    padding: 8px 5px;
    padding-bottom: calc(8px + env(safe-area-inset-bottom, 0));
    box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.3);
    z-index: 0;
}

.nav-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    color: var(--text-secondary);
    padding: 8px 2px;
    flex: 1 1 0;
    border-radius: 12px;
    transition: all 0.2s ease;
    min-width: 0;
    min-height: 44px;
}

.nav-item.active {
    color: var(--color-accent);
    background-color: #2d271f;
}

.nav-label {
    margin-top: 5px;
    font-size: 10px;
    font-weight: 500;
    text-align: center;
    white-space: nowrap;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
}

.icon-wrapper {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
}

.action-badge {
    position: absolute;
    top: -6px;
    right: -10px;
    background: var(--color-accent);
    color: #121b2f;
    font-size: 10px;
    font-weight: 700;
    min-width: 18px;
    height: 18px;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 4px;
    border: 2px solid var(--bg-main);
}
</style>
