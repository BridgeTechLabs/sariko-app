import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth/authStore'
import { apiLaunch } from '@/apis/launch/apiLaunch'

let _bootstrapped = false

const routes = [
    {
        path: '/',
        redirect: '/home'
    },
    {
        path: '/dummy',
        name: 'dummy',
        component: () => import('@/pages/OrdersPage.vue')
    },
    {
        path: '/home',
        name: 'home',
        component: () => import('@/pages/HomePage.vue'),
        meta: { buyer: true }
    },
    {
        path: '/signin',
        name: 'signin',
        component: () => import('@/pages/auth/AuthPage.vue'),
        meta: { guestOnly: true }
    },
    {
        path: '/signup',
        name: 'signup',
        component: () => import('@/pages/auth/AuthPage.vue'),
        meta: { guestOnly: true }
    },
    {
        path: '/forgot-password',
        name: 'forgot-password',
        component: () => import('@/pages/ForgotPasswordPage.vue'),
        meta: { guestOnly: true }
    },
    {
        path: '/reset-password',
        name: 'reset-password',
        component: () => import('@/pages/ResetPasswordPage.vue'),
    },
    {
        path: '/onboarding',
        name: 'onboarding',
        component: () => import('@/pages/Onboarding.vue'),
        meta: { requiresAuth: true }
    },
    {
        // Public seller application. Not "onboarding": /onboarding is the buyer's phone + address setup.
        path: '/join',
        name: 'join',
        component: () => import('@/pages/JoinPage.vue'),
    },
    {
        path: '/sellers',
        name: 'all-sellers',
        component: () => import('@/pages/AllSellersPage.vue'),
        meta: { buyer: true }
    },
    {
        path: '/search',
        name: 'search',
        component: () => import('@/pages/SearchPage.vue'),
        meta: { buyer: true }
    },
    {
        path: '/seller/:slugName',
        name: 'seller',
        component: () => import('@/pages/SellerPage.vue'),
        props: true,
        meta: { buyer: true }
    },
    {
        path: '/food/:sellerSlug/:foodId',
        name: 'food-detail',
        component: () => import('@/pages/FoodDetailPage.vue'),
        props: true,
        meta: { buyer: true }
    },
    {
        path: '/cart',
        name: 'cart',
        component: () => import('@/pages/CartPage.vue'),
        meta: { requiresAuth: true, buyer: true }
    },
    // {
    //     path: '/checkout',
    //     name: 'checkout',
    //     component: () => import('@/pages/CheckoutPage.vue')
    // },
    {
        path: '/payment/return',
        name: 'payment-return',
        component: () => import('@/pages/PaymentReturnPage.vue')
    },
    {
        path: '/orders',
        name: 'orders',
        component: () => import('@/pages/OrdersPage.vue'),
        meta: { requiresAuth: true, buyer: true }
    },
    {
        path: '/orders/:orderId',
        name: 'order-confirmation',
        component: () => import('@/pages/OrderConfirmationPage.vue'),
        props: true,
        meta: { requiresAuth: true, buyer: true }
    },
    {
        path: '/orders/:orderId/review',
        name: 'order-review',
        component: () => import('@/pages/OrderReviewPage.vue'),
        props: true,
        meta: { requiresAuth: true, buyer: true }
    },
    // T35 complaints (buyer and seller): new before :complaintId
    {
        path: '/complaints',
        name: 'complaints',
        component: () => import('@/pages/ComplaintsPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/complaints/new',
        name: 'complaint-new',
        component: () => import('@/pages/ComplaintNewPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/complaints/:complaintId',
        name: 'complaint-detail',
        component: () => import('@/pages/ComplaintDetailPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/dashboard',
        redirect: '/seller/home'
    },
    {
        path: '/seller/home',
        name: 'seller-home',
        component: () => import('@/pages/seller/SellerHomePage.vue'),
        meta: { requiresAuth: true, requiresSeller: true }
    },
    {
        path: '/seller/orders',
        name: 'seller-orders',
        component: () => import('@/pages/seller/SellerOrdersPage.vue'),
        meta: { requiresAuth: true, requiresSeller: true }
    },
    {
        path: '/seller/orders/:orderId',
        name: 'seller-order-detail',
        component: () => import('@/pages/seller/SellerOrderDetailPage.vue'),
        props: true,
        meta: { requiresAuth: true, requiresSeller: true }
    },
    {
        path: '/seller/menu',
        name: 'seller-menu',
        component: () => import('@/pages/seller/SellerMenuPage.vue'),
        meta: { requiresAuth: true, requiresSeller: true }
    },
    {
        path: '/seller/me',
        name: 'seller-me',
        component: () => import('@/pages/seller/SellerMePage.vue'),
        meta: { requiresAuth: true, requiresSeller: true }
    },
    {
        path: '/seller/me/profile',
        name: 'seller-profile-completion',
        component: () => import('@/pages/seller/SellerProfileCompletionPage.vue'),
        meta: { requiresAuth: true, requiresSeller: true }
    },
    {
        path: '/account',
        name: 'account',
        component: () => import('@/pages/AccountPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/account/profile',
        name: 'account-profile',
        component: () => import('@/pages/EditProfilePage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/account/address',
        name: 'account-address',
        component: () => import('@/pages/DeliveryAddressPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/account/language',
        name: 'account-language',
        component: () => import('@/pages/LanguagePage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/account/change-password',
        name: 'account-change-password',
        component: () => import('@/pages/ChangePasswordPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/account/terms',
        name: 'account-terms',
        component: () => import('@/pages/TermsPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/notifications',
        name: 'notifications',
        component: () => import('@/pages/NotificationsPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/chat',
        name: 'chat',
        component: () => import('@/pages/ChatListPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/chat/:conversationId',
        name: 'conversation',
        component: () => import('@/pages/ConversationPage.vue'),
        props: true,
        meta: { requiresAuth: true }
    },
    {
        path: '/v2/account',
        name: 'account-v2',
        component: () => import('@/pages/v2/account/AccountPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/v2/account/addresses',
        name: 'account-addresses-v2',
        component: () => import('@/pages/v2/account/AddressesPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/v2/account/addresses/new',
        name: 'account-address-new-v2',
        component: () => import('@/pages/v2/account/AddressFormPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/v2/account/addresses/:id/edit',
        name: 'account-address-edit-v2',
        component: () => import('@/pages/v2/account/AddressFormPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/v2/account/language',
        name: 'account-language-v2',
        component: () => import('@/pages/v2/account/LanguagePage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/v2/account/change-password',
        name: 'account-change-password-v2',
        component: () => import('@/pages/v2/account/ChangePasswordPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/v2/account/edit-profile',
        name: 'account-edit-profile-v2',
        component: () => import('@/pages/v2/account/EditProfilePage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/v2/account/terms',
        name: 'account-terms-v2',
        component: () => import('@/pages/v2/account/TermsPage.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/coming-soon',
        name: 'coming-soon',
        component: () => import('@/pages/ComingSoonPage.vue'),
    },
    {
        path: '/:pathMatch(.*)*',
        name: 'not-found',
        component: () => import('@/pages/NotFoundPage.vue'),
    }
]

export const router = createRouter({
    history: createWebHistory(),
    routes,
    scrollBehavior(to, from, savedPosition) {
        if (savedPosition) {
            return savedPosition
        } else {
            return { top: 0 }
        }
    }
})

router.beforeEach(async (to) => {
    const authStore = useAuthStore()

    if (!_bootstrapped) {
        await authStore.bootstrap()
        _bootstrapped = true
    }

    const isLoggedIn = !!authStore.user

    if (to.meta.requiresAuth && !isLoggedIn) {
        return { name: 'signin', query: { redirect: to.fullPath } }
    }

    if (to.meta.guestOnly && isLoggedIn) {
        return { name: authStore.user?.isSeller ? 'seller-home' : 'home' }
    }

    if (to.name === 'home' && isLoggedIn && authStore.user?.isSeller) {
        return { name: 'seller-home' }
    }

    if (to.name === 'account' && isLoggedIn && authStore.user?.isSeller) {
        return { name: 'seller-me' }
    }

    if (to.meta.requiresSeller && (!authStore.user?.isSeller)) {
        return { name: 'home' }
    }

    // Until admin_settings app_live = 1 (go live), buyer pages show /coming-soon. ?preview=1 (remembered
    // in this browser, ?preview=0 to stop) lets testers through. This is a notice, not a lock: the
    // backend still takes orders, so test orders before launch rely on only the test store being listed.
    if (to.query.preview === '1' || to.query.preview === '0') {
        try { to.query.preview === '1' ? localStorage.setItem('preview', '1') : localStorage.removeItem('preview') } catch { }
    }
    if (to.meta.buyer || to.name === 'coming-soon') {
        let preview = false
        try { preview = localStorage.getItem('preview') === '1' } catch { }
        const { prelaunch } = await apiLaunch.get()
        if (to.meta.buyer && prelaunch && !preview) return { name: 'coming-soon' }
        if (to.name === 'coming-soon' && !prelaunch) return { name: 'home' }
    }
})

export default function useRouterPlugin(app) {
    console.log("Loaded Vue Router plugin")
    app.use(router);
}

