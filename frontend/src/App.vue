<script>
import BottomNavigation from '@/components/nav/BottomNavigation.vue'
import SellerBottomNav from '@/components/nav/SellerBottomNav.vue'
import { defineAsyncComponent } from 'vue'
import { setUpAxiosPolicy } from "@/lib/axiosPolicy.js";
import { useAuthStore } from '@/stores/auth/authStore'
import { useChatStore } from '@/stores/chat/chatStore'

// Dev panel (Ctrl+Shift+Q) only in builds with VITE_DEV_PANEL=true (local, DEV).
// Vite inlines the flag at build time, so the prod bundle doesn't contain the panel.
const DevPanel = import.meta.env.VITE_DEV_PANEL === 'true'
    ? defineAsyncComponent(() => import('@/components/dev/HackerPanel.vue'))
    : null

export default {
    name: 'App',
    components: {
        BottomNavigation,
        SellerBottomNav,
    },

    setup() {
        setUpAxiosPolicy();
        return { DevPanel }
    },

    data() {
        return {}
    },
    computed: {
        isSeller() {
            return !!useAuthStore().user?.isSeller
        },
        userId() {
            return useAuthStore().user?.id || null
        },
        showNavigation() {
            const hiddenRoutes = ['food-detail', 'forgot-password', 'reset-password', 'signin', 'signup', 'all-sellers', 'conversation', 'seller', 'order-review', 'account-addresses-v2', 'account-address-new-v2', 'account-address-edit-v2', 'account-terms-v2', 'account-change-password-v2', 'account-edit-profile-v2', 'join']
            return !hiddenRoutes.includes(this.$route.name)
        }
    },
    watch: {
        // Keep the app-wide unread badge live: load counts + open the global
        // subscription once logged in, tear it down on logout.
        userId: {
            immediate: true,
            handler(id) {
                const chat = useChatStore()
                if (id) {
                    chat.loadConversations(this.isSeller)
                    chat.subscribeGlobalUnread()
                } else {
                    chat.unsubscribeGlobalUnread()
                }
            }
        }
    },
    methods: {}
}
</script>

<template>
    <div class="background">
        <!-- /join gets a wider column on desktop: its Menu step is a table -->
        <div class="app-container" :class="{ 'app-container--wide': $route.name === 'join' }">
            <router-view/>
            <!-- <router-view v-slot="{ Component }"> -->
                <!-- <transition name="fade" mode="out-in">
                    <component :is="Component" />
                </transition> -->
            <!-- </router-view> -->
        </div>
        <SellerBottomNav v-if="showNavigation && isSeller" />
        <BottomNavigation v-else-if="showNavigation" />
        <component :is="DevPanel" v-if="DevPanel" />
    </div>    
</template>

<style scoped>

.app-container {
    min-height: 100vh;
    min-height: 100dvh;
    max-width: 800px;
    display: flex;
    flex-direction: column;
    margin: auto;
}

.app-container--wide {
    max-width: 1100px;
}

.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}
</style>