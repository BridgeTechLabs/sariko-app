import { defineStore } from "pinia";
import { router } from "@/plugins/router";
import { Notify } from "quasar";
import { supabase } from "@/lib/supabase";
import apiAuth from "@/apis/auth/apiAuth";
import apiUsers from "@/apis/users/apiUsers";
import { useCartStore } from "@/stores/cart/cartStore";
import { useOrderStore } from "@/stores/order/orderStore";
import { useChatStore } from "@/stores/chat/chatStore";
import { useDeliveryStore } from "@/stores/delivery/deliveryStore";
import { useDashboardStore } from "@/stores/seller/dashboardStore";
import { useMenuStore } from "@/stores/seller/menuStore";
import { useProfileCompletionStore } from "@/stores/seller/profileCompletionStore";
import { useReviewStore } from "@/stores/review/reviewStore";
import { useComplaintStore } from "@/stores/complaint/complaintStore";
import { useAddressStore } from "@/stores/address/addressStore";
import { i18n } from "@/plugins/i18n";
import { disablePush } from "@/composables/pushNotifications";

const LANG_MAP = { 'Tiếng Việt': 'vi', 'English': 'en_ph', 'Fillipino': 'en_ph' };

const ROLE_KEY = 'sariko.role';
const ROLE_USER_KEY = 'sariko.roleUserId';

let _redirectingToSignIn = false;

// Sign-out is a route change, not a reload: drop every store that holds the old account's data.
// Stores with a poller / channel have their own reset() that stops it first; orderStore keeps its
// poller handles (a $reset() would drop them while the intervals keep running), so only its data goes.
function resetAccountStores() {
    useCartStore().$reset();
    const orderStore = useOrderStore();
    orderStore.orders = [];
    orderStore.currentOrder = null;
    useChatStore().reset();
    useDeliveryStore().reset();
    useDashboardStore().reset();
    useMenuStore().$reset();
    useProfileCompletionStore().$reset();
    useReviewStore().$reset();
    useComplaintStore().$reset();
    useAddressStore().$reset();
}

// The axios interceptor reads the token via supabase.auth.getSession() (storage),
// so wait until the new session is persisted before anything calls the API.
async function waitForStoredSession(accessToken, timeoutMs = 5000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
        const { data } = await supabase.auth.getSession();
        if (data?.session?.access_token === accessToken) return data.session;
        await new Promise((r) => setTimeout(r, 100));
    }
    throw new Error("Session was not persisted in time");
}

function getStoredRole(userId) {
    try {
        if (!userId) return null;
        if (localStorage.getItem(ROLE_USER_KEY) !== userId) return null;
        const role = localStorage.getItem(ROLE_KEY);
        if (role === 'seller') return true;
        if (role === 'buyer') return false;
        return null;
    } catch { return null; }
}

function setStoredRole(userId, isSeller) {
    try {
        if (!userId) return;
        localStorage.setItem(ROLE_KEY, isSeller ? 'seller' : 'buyer');
        localStorage.setItem(ROLE_USER_KEY, userId);
    } catch {}
}

function clearStoredRole() {
    try {
        localStorage.removeItem(ROLE_KEY);
        localStorage.removeItem(ROLE_USER_KEY);
    } catch {}
}

function applyLocale(preferredLanguage) {
    if (!preferredLanguage) return;
    const locale = LANG_MAP[preferredLanguage] || 'en_ph';
    i18n.global.locale = locale;
    localStorage.setItem('lang', locale);
}

// What a buyer still needs before checkout: the cart blocks Place order on these, the home banner lists them.
export const BUYER_MISSING_ROUTES = { phone: '/account/profile', address: '/account/address' };

export const useAuthStore = defineStore("authStore", {
    state() {
        return {
            // signin
            inputSignInEmail: '',
            inputSignInPassword: '',

            // signup
            inputSignUpFullName: '',
            inputSignUpEmail: '',
            inputSignUpPassword: '',
            isSelectedSignUpRoleSeller: false,
            inputSignUpAgreed: false,

            // errors state
            errors: {
                inputSignInEmail: null,
                inputSignInPassword: null,
                inputSignUpFullName: null,
                inputSignUpEmail: null,
                inputSignUpPassword: null
            },

            // onborading user
            inputPhoneNumber: null,
            inputAddress: null,
            inputAddressDetails: null,
            inputLat: null,
            inputLon: null,
            // delivery address of the next order (default one, or picked in the cart): addressStore.useForOrder
            inputReceiverName: null,
            inputReceiverPhone: null,
            inputDeliveryNote: null,   // street_name · note, for the driver
            selectedPreferedLanguage: 'English',

            // user & session
            session: null,
            user: null,
            isLoading: false,
            sellerId: null,
            buyerInfoLoaded: false,  // profile + address fetched for this session (no banner flash while loading)

            // auth subscription
            _authSub: null,
            isPasswordRecovery: false,
        }
    },

    getters: {
        buyerMissing: (state) => Object.keys(BUYER_MISSING_ROUTES).filter((k) =>
            k === 'phone' ? !state.user?.phone : !state.inputAddress),
    },

    actions: {

        _setFromSession(session) {
            this.session = session;
            if (session?.user) {
                const meta = session.user.user_metadata || {};
                const cachedRole = getStoredRole(session.user.id);
                this.user = {
                    id: session.user.id,
                    fullName: meta.fullname || this.user?.fullName || '',
                    email: session.user.email,
                    phone: this.user?.phone || null,
                    isSeller: cachedRole ?? this.user?.isSeller ?? false,
                    avatarUrl: this.user?.avatarUrl || null,
                    sellerId: this.user?.sellerId || null
                };
            } else {
                this.session = null;
                this.user = null;
                clearStoredRole();
            }
        },

        async bootstrap() {
            if (this._authSub) return;
            // Subscribe before any await: supabase-js fires PASSWORD_RECOVERY / SIGNED_IN
            // from a URL callback only once, right after init, and late subscribers miss it.
            const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
                if (event === 'INITIAL_SESSION') return;
                if (event === 'PASSWORD_RECOVERY') {
                    this.isPasswordRecovery = true;
                    return;
                }
                this._setFromSession(session);
            });
            this._authSub = subscription;
            try {
                const res = await apiAuth.authGetSession();
                if (res?.session) {
                    this._setFromSession(res.session);

                    try {
                        const profile = await apiUsers.getProfile()
                        if (profile?.user && this.user) {
                            if (profile.user.avatar_url) this.user.avatarUrl = profile.user.avatar_url
                            if (profile.user.name) this.user.fullName = profile.user.name
                            if (profile.user.phone) this.user.phone = profile.user.phone
                            if (profile.user.seller_id) this.sellerId = profile.user.seller_id
                            if (profile.user.is_seller !== undefined && getStoredRole(this.user.id) === null) {
                                this.user.isSeller = profile.user.is_seller
                                setStoredRole(this.user.id, profile.user.is_seller)
                            }
                            applyLocale(profile.user.preferred_language)
                        }
                    } catch (e) {
                        console.error(`authStore - bootstrap - profile fetch failed: ${e}`);
                    }

                    try {
                        await useAddressStore().fetch()   // fills input* from the default address
                    } catch (e) {
                        console.error(`authStore - bootstrap - address fetch failed: ${e}`);
                    }
                    this.buyerInfoLoaded = true;

                    try {
                        const cartStore = useCartStore();
                        await cartStore.getCurrentCart();
                    } catch (e) {
                        console.error(`authStore - bootstrap - cart preload failed: ${e}`);
                    }

                    try {
                        const orderStore = useOrderStore();
                        await orderStore.getOrders();
                    } catch (e) {
                        console.error(`authStore - bootstrap - orders preload failed: ${e}`);
                    }
                }
            } catch (e) {
                console.error(`authStore - bootstrap - ${e}`);
            }
        },

        async refreshProfile() {
            try {
                const profile = await apiUsers.getProfile()
                if (profile?.user && this.user) {
                    if (profile.user.avatar_url) this.user.avatarUrl = profile.user.avatar_url
                    if (profile.user.name) this.user.fullName = profile.user.name
                    if (profile.user.phone) this.user.phone = profile.user.phone
                    if (profile.user.seller_id) this.sellerId = profile.user.seller_id
                    if (profile.user.is_seller !== undefined && getStoredRole(this.user.id) === null) {
                        this.user.isSeller = profile.user.is_seller
                        setStoredRole(this.user.id, profile.user.is_seller)
                    }
                }
            } catch (e) {
                console.error(`authStore - refreshProfile - ${e}`)
            }
        },

        async getValidAccessToken() {
            const res = await apiAuth.authGetSession();
            if (!res?.session) return null;

            const now = Math.floor(Date.now() / 1000);
            const exp = res.session.expires_at ?? 0;

            if (exp - now < 30) {
                const { data, error } = await supabase.auth.refreshSession();
                if (error) throw error;
                this._setFromSession(data.session);
                return data.session?.access_token ?? null;
            }
            return res.session.access_token;
        },

        // validation
        validateField(field) {
            switch (field) {
                case "inputSignInEmail":
                case "inputSignUpEmail": {
                    const value = this[field]?.trim();
                    this.errors[field] = !value
                        ? "Email is required."
                        : /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
                        ? null
                        : "Invalid email format.";
                    break;
                }
                // Sign-in only checks presence: accounts created before the 8-char rule still have 6-7 char passwords
                case "inputSignInPassword":
                    this.errors[field] = !this[field] ? "Password is required." : null;
                    break;
                case "inputSignUpPassword": {
                    const value = this[field];
                    this.errors[field] = !value
                        ? "Password is required."
                        : value.length < 8
                        ? "Password must be at least 8 characters."
                        : null;
                    break;
                }
                case "inputSignUpFullName":
                    this.errors.inputSignUpFullName = !this.inputSignUpFullName?.trim()
                        ? "Full name is required."
                        : null;
                    break;
            }
        },

        validateAllFields(mode = "signin") {
            if (mode === "signin") {
                this.validateField("inputSignInEmail");
                this.validateField("inputSignInPassword");
            } else {
                this.validateField("inputSignUpEmail");
                this.validateField("inputSignUpPassword");
                this.validateField("inputSignUpFullName");
            }
            return !Object.values(this.errors).some((e) => !!e);
        },

        // auth actions
        async onClickedSignin() {
            const isValid = this.validateAllFields("signin");
            if (!isValid) return;

            this.isLoading = true;
            try {
                const res = await apiAuth.authSignin(
                    this.inputSignInEmail,
                    this.inputSignInPassword
                );
                if (!res?.session || !res?.user) throw new Error("No user data");

                // Setting user triggers App.vue to load conversations — token must be stored first
                const session = await waitForStoredSession(res.session.access_token);
                this._setFromSession(session);
                this.buyerInfoLoaded = false;

                try {
                    const profile = await apiUsers.getProfile()
                    if (profile?.user && this.user) {
                        if (profile.user.avatar_url) this.user.avatarUrl = profile.user.avatar_url
                        if (profile.user.name) this.user.fullName = profile.user.name
                        if (profile.user.phone) this.user.phone = profile.user.phone
                        if (profile.user.seller_id) this.sellerId = profile.user.seller_id
                        if (profile.user.is_seller !== undefined) {
                            this.user.isSeller = profile.user.is_seller
                            setStoredRole(this.user.id, profile.user.is_seller)
                        }
                        applyLocale(profile.user.preferred_language)
                    }
                } catch (e) {
                    console.error(`authStore - onClickedSignin - profile fetch failed: ${e}`);
                }

                try {
                    await useAddressStore().fetch()   // fills input* from the default address
                } catch (e) {
                    console.error(`authStore - onClickedSignin - address fetch failed: ${e}`);
                }
                this.buyerInfoLoaded = true;

                try {
                    const cartStore = useCartStore();
                    await cartStore.getCurrentCart();
                } catch (e) {
                    console.error(`authStore - onClickedSignin - cart preload failed: ${e}`);
                }

                try {
                    const orderStore = useOrderStore();
                    await orderStore.getOrders();
                } catch (e) {
                    console.error(`authStore - onClickedSignin - orders preload failed: ${e}`);
                }

                Notify.create({
                    classes: 'quasar-notify-positive',
                    message: "👋 Welcome to Sariko",
                    progress: true,
                    position: "bottom",
                });
                const defaultRoute = this.user?.isSeller ? '/seller/home' : '/home'
                const redirect = router.currentRoute.value.query.redirect || defaultRoute;
                router.push(redirect);

            } catch (error) {
                console.error(`authStore - onClickedSignin - ${error}`);
                let errorMessage = null;
                if (error?.code === "invalid_credentials") {
                    errorMessage = "Incorrect email or password. Please try again.";
                }
                Notify.create({
                    classes: 'quasar-notify-negative',
                    message: errorMessage || "An unexpected error has occurred. Please try again.",
                    progress: true,
                    icon: 'fa-regular fa-circle-xmark',
                    position: "bottom",
                });
            } finally {
                this.isLoading = false;
            }
        },

        async onClickedSignup() {
            const isValid = this.validateAllFields("signup");
            if (!isValid || !this.inputSignUpAgreed) return;

            this.isLoading = true;
            try {
                const res = await apiAuth.authSignup(
                    this.inputSignUpEmail,
                    this.inputSignUpPassword,
                    this.inputSignUpFullName,
                    this.isSelectedSignUpRoleSeller,
                );
                if (res?.session && res?.user) {
                    const session = await waitForStoredSession(res.session.access_token);
                    this._setFromSession(session);
                    if (this.user) {
                        this.user.isSeller = this.isSelectedSignUpRoleSeller;
                        setStoredRole(this.user.id, this.isSelectedSignUpRoleSeller);
                    }
                    Notify.create({
                        classes: 'quasar-notify-positive',
                        message: i18n.global.t("common.toast_welcome"),
                        progress: true,
                        icon: 'fa-regular fa-circle-check',
                        position: "bottom",
                    });
                    router.push({ name: "onboarding" });
                }
            } catch (error) {
                console.error(`authStore - onClickedSignup - ${error}`);
                let errorMessage = null;
                if (error?.code === "user_already_exists") {
                    errorMessage = "An account with this email already exists. Please sign in or use a different email.";
                }
                Notify.create({
                    classes: 'quasar-notify-negative',
                    message: errorMessage || "An unexpected error has occurred. Please try again.",
                    progress: true,
                    icon: 'fa-regular fa-circle-xmark',
                    position: "bottom",
                });
            } finally {
                this.isLoading = false;
            }
        },

        async onClickedSignout() {
            try {
                // Shared phone: stop this device getting the old account's order pushes
                await disablePush().catch((error) => console.warn(`authStore - disablePush - ${error}`));
                await apiAuth.authSignout();
                // Sign-out is a route change, not a reload: drop the old account's address, phone, flags
                const sub = this._authSub;
                this.$reset();
                this._authSub = sub;
                clearStoredRole();
                resetAccountStores();
                Notify.create({
                    classes: 'quasar-notify-positive',
                    message: i18n.global.t("common.toast_signed_out"),
                    progress: true,
                    icon: 'fa-regular fa-circle-check',
                    position: "bottom",
                });
                router.push('/home');
            } catch (error) {
                console.error(`authStore - onClickedSignout - ${error}`);
            }
        },

        async signOutRedirectSignIn() {
            // Several requests can 401 at once — redirect only once
            if (_redirectingToSignIn) return;
            _redirectingToSignIn = true;
            try {
                await apiAuth.authSignout();
            } catch (error) {
                console.error(`authStore - signOutRedirectSignIn - ${error}`);
            }
            const sub = this._authSub;
            this.$reset();
            this._authSub = sub;
            clearStoredRole();
            resetAccountStores();
            Notify.create({
                classes: 'quasar-notify-negative',
                message: i18n.global.t("common.toast_session_expired"),
                progress: true,
                icon: 'fa-regular fa-circle-xmark',
                position: "bottom",
            });
            const current = router.currentRoute.value;
            try {
                if (current.name !== 'signin') {
                    await router.push({ name: 'signin', query: { redirect: current.fullPath } });
                }
            } finally {
                _redirectingToSignIn = false;
            }
        },
    }
})