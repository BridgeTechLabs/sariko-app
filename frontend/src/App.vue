<script>
import BottomNavigation from '@/components/nav/BottomNavigation.vue'
import SellerBottomNav from '@/components/nav/SellerBottomNav.vue'
import HackerPanel from '@/components/dev/HackerPanel.vue'
import { setUpAxiosPolicy } from "@/lib/axiosPolicy.js";
import { useAuthStore } from '@/stores/auth/authStore'
import { useChatStore } from '@/stores/chat/chatStore'

export default {
    name: 'App',
    components: {
        BottomNavigation,
        SellerBottomNav,
        HackerPanel,
    },

    setup() {
        setUpAxiosPolicy();
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
            const hiddenRoutes = ['food-detail', 'forgot-password', 'reset-password', 'signin', 'signup', 'all-sellers', 'conversation', 'seller', 'order-review', 'account-addresses-v2', 'account-address-new-v2', 'account-address-edit-v2', 'account-terms-v2', 'account-change-password-v2']
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
        <div class="app-container">
            <router-view/>
            <!-- <router-view v-slot="{ Component }"> -->
                <!-- <transition name="fade" mode="out-in">
                    <component :is="Component" />
                </transition> -->
            <!-- </router-view> -->
        </div>
        <SellerBottomNav v-if="showNavigation && isSeller" />
        <BottomNavigation v-else-if="showNavigation" />
        <HackerPanel />
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

.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}
</style>