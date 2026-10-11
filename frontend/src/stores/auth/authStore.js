import { defineStore } from "pinia";
import { router } from "@/plugins/router";
import { Notify } from "quasar";
import { supabase } from "@/lib/supabase";
import apiAuth from "@/apis/auth/apiAuth";
import apiUsers from "@/apis/users/apiUsers";
import { useCartStore } from "@/stores/cart/cartStore";
import { useOrderStore } from "@/stores/order/orderStore";
import { i18n } from "@/plugins/i18n";
import { disablePush } from "@/composables/pushNotifications";

const LANG_MAP = { 'Tiếng Việt': 'vi', 'English': 'en_ph', 'Fillipino': 'en_ph' };

const ROLE_KEY = 'sariko.role';
const ROLE_USER_KEY = 'sariko.roleUserId';

let _redirectingToSignIn = false;

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
            selectedPreferedLanguage: 'English',

            // user & session
            session: null,
            user: null,
            isLoading: false,
            sellerId: null,

            // auth subscription
            _authSub: null,
            isPasswordRecovery: false,
        }
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
                        const addrRes = await apiUsers.getDefaultAddress()
                        if (addrRes?.address) {
                            this.inputAddress = addrRes.address.address || null
                            this.inputAddressDetails = addrRes.address.label || null
                            this.inputLat = addrRes.address.lat || null
                            this.inputLon = addrRes.address.lon || null
                        }
                    } catch (e) {
                        console.error(`authStore - bootstrap - address fetch failed: ${e}`);
                    }

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

                const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
                    if (event === 'INITIAL_SESSION') return;
                    if (event === 'PASSWORD_RECOVERY') {
                        this.isPasswordRecovery = true;
                        return;
                    }
                    this._setFromSession(session);
                });
                this._authSub = subscription;
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
                case "inputSignInPassword":
                case "inputSignUpPassword": {
                    const value = this[field];
                    this.errors[field] = !value
                        ? "Password is required."
                        : value.length < 6
                        ? "Password must be at least 6 characters."
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
                    const addrRes = await apiUsers.getDefaultAddress()
                    if (addrRes?.address) {
                        this.inputAddress = addrRes.address.address || null
                        this.inputAddressDetails = addrRes.address.label || null
                        this.inputLat = addrRes.address.lat || null
                        this.inputLon = addrRes.address.lon || null
                    }
                } catch (e) {
                    console.error(`authStore - onClickedSignin - address fetch failed: ${e}`);
                }

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
            if (!isValid) return;

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
                        message: "Welcome to Sariko! Let's set up your profile.",
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
                this.session = null;
                this.user = null;
                clearStoredRole();
                useCartStore().$reset();
                Notify.create({
                    classes: 'quasar-notify-positive',
                    message: "Signed out successfully.",
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
            this.session = null;
            this.user = null;
            clearStoredRole();
            useCartStore().$reset();
            Notify.create({
                classes: 'quasar-notify-negative',
                message: "Session expired. Please log in again.",
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