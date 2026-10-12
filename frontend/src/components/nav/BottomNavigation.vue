<script>
import { House, ShoppingCart, Clipboard, Bell, CircleUserRound } from 'lucide-vue-next';
import { useCartStore } from '@/stores/cart/cartStore';
import { useOrderStore } from '@/stores/order/orderStore';
import { useChatStore } from '@/stores/chat/chatStore';

export default {
    name: 'BottomNavigation',

    components: { House, ShoppingCart, Clipboard, Bell, CircleUserRound },

    computed: {
        cartBadge() {
            return useCartStore().itemCount
        },
        unpaidBadge() {
            return useOrderStore().unpaidCount
        },
        inboxBadge() {
            return useChatStore().totalUnread
        },
        isShow() {
            const path = this.$route.path
            return path != '/signin'
                && path != '/signup'
                && path != '/cart'
                && path != '/dummy'
                && path != '/onboarding'
                && path != '/payment/return'
                && !path.match(/^\/orders\/[^/]+$/)
                && !path.match(/^\/account\/.+$/)
                && !path.match(/^\/food\/.+$/)
        }
    },

    methods: {
        isActive(path) {
            if (path === '/home') {
                return this.$route.path === '/' || this.$route.path === '/home'
            }
            return this.$route.path.startsWith(path)
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
        <router-link to="/home" class="nav-item" :class="{ active: isActive('/home') }">
            <House size="18px" />
            <div class="nav-label">{{ $t('bottom_nav.button_label_home') }}</div>
        </router-link>

        <router-link to="/orders" class="nav-item" :class="{ active: isActive('/orders') }">
            <div class="icon-wrapper">
                <Clipboard size="18px" />
                <span v-if="unpaidBadge > 0" class="order-badge">{{ unpaidBadge }}</span>
            </div>
            <div class="nav-label">{{ $t('bottom_nav.button_label_orders') }}</div>
        </router-link>

        <router-link to="/cart" class="nav-item">
            <div class="icon-cart">
                <ShoppingCart size="18px" style="color: #2d271f"/>
                <span v-if="cartBadge > 0" class="cart-badge">{{ cartBadge }}</span>
            </div>
            <div class="nav-label">{{ $t('bottom_nav.button_label_cart') }}</div>
        </router-link>

        <div class="nav-item disabled">
            <Bell size="18px" />
            <div class="nav-label">{{ $t('bottom_nav.button_label_notifications') }}</div>
        </div>

        <router-link to="/account" class="nav-item" :class="{ active: isActive('/account') }">
            <div class="icon-wrapper">
                <CircleUserRound size="18px" />
                <span v-if="inboxBadge > 0" class="order-badge">{{ inboxBadge }}</span>
            </div>
            <div class="nav-label">{{ $t('bottom_nav.button_label_account') }}</div>
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
    padding: 8px 16px;
    border-radius: 12px;
    transition: all 0.2s ease;
    position: relative;
    min-width: 64px;
    min-height: 44px;
}

.icon-cart {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f5A623;
}

.cart-badge {
    position: absolute;
    top: -4px;
    right: -4px;
    background: #ef4444;
    color: #fff;
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

.icon-wrapper {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
}

.order-badge {
    position: absolute;
    top: -6px;
    right: -10px;
    background: #ef4444;
    color: #fff;
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

.nav-item.active {
    color: var(--color-accent);
    background-color: #2d271f;
}

.nav-label {
    margin-top: 5px;
    font-size: 10px;
    font-weight: 500;
}

.nav-item.disabled {
    opacity: 0.35;
    pointer-events: none;
}
</style>
