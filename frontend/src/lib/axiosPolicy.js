import axios from "axios";
import { useRouter } from "vue-router";
import { Notify } from "quasar";
import { useAuthStore } from "@/stores/auth/authStore.js";
import { supabase } from "@/lib/supabase";
import { i18n } from "@/plugins/i18n";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/rest";

// downloadClient.interceptors.request.use(function (config) {
//     const authStore = useAuthStore();
//     const session = authStore.session;
//     if (session?.access_token) {
//         config.headers.Authorization = `Bearer ${session.access_token}`;
//     }
//     return config;
// });

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
        "Content-Type": "application/json",
    },
});

let reqId = null;
let resId = null;
let refreshingPromise = null; 

function toast(message, type = "negative", timeout = 4000) {
    Notify.create({ type, timeout, message, position: "top-right" });
}

// Backend `detail` is fixed English text (or {code, message, ...params}); this maps it to
// api_errors.* in the locale files. Anything unmapped shows api_errors.generic, so users
// never see raw English; the original stays in the console.
const ERROR_KEYS = {
    "Cart is empty": "cart_empty",
    "Duplicate order detected. Please wait.": "duplicate_order",
    "This store is closed now. Same-day dishes can't be ordered; pre-order dishes still can.": "store_closed",
    "This dish is sold out": "dish_sold_out",
    "This price option is sold out": "option_sold_out",
    "Please choose a price option": "choose_option",
    "Cart contains items from another seller": "another_seller",
    "Seller location not configured": "seller_location_missing",
    "Could not get a delivery fee quote. Please try again.": "delivery_quote_failed",
    "This order can't be cancelled now": "cannot_cancel_now",
    "Order status changed, please refresh": "order_status_changed",
    "Order already paid": "order_already_paid",
    "Order already reviewed": "already_reviewed",
    "Max rebook attempts reached": "rebook_max_reached",
    "Unable to book a delivery driver. Your order has been cancelled.": "booking_failed_cancelled",
    "Missing pickup or dropoff address. Please update your store address in settings.": "store_address_missing",
    "You already have a dish with this name in this category": "dish_name_taken",
    "This price option is in a customer's cart. Hide it instead of deleting.": "option_in_cart",
    "Cannot unset the default address; set another address as default instead": "cannot_unset_default_address",
    "Invalid phone number": "invalid_phone",
    "Cannot start a conversation with your own store": "own_store_chat",
    "Driver has already picked up the order": "driver_picked_up",
};

export function apiErrorMessage(data, fallbackKey = "generic") {
    const t = i18n.global.t;
    const detail = data?.detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
        if (detail.code && i18n.global.te(`api_errors.${detail.code}`)) return t(`api_errors.${detail.code}`, detail);
        if (ERROR_KEYS[detail.message]) return t(`api_errors.${ERROR_KEYS[detail.message]}`);
    }
    if (typeof detail === "string" && ERROR_KEYS[detail]) return t(`api_errors.${ERROR_KEYS[detail]}`);
    if (detail) console.warn("Untranslated API error:", detail);
    return t(`api_errors.${fallbackKey}`);
}

async function getToken(authStore) {
    
    try {
        if (typeof authStore?.getValidAccessToken === "function") {
            return await authStore.getValidAccessToken();
        }
        const {
            data: { session },
        } = await supabase.auth.getSession();

        return session?.access_token || null;
    } catch (error) {
        console.error("An error has occured in getToken: ", error)
        return null;
    }
}

export const setUpAxiosPolicy = () => {
    
    if (reqId !== null) {
        apiClient.interceptors.request.eject(reqId);
        reqId = null;
    }
    if (resId !== null) {
        apiClient.interceptors.response.eject(resId);
        resId = null;
    }

    const authStore = useAuthStore();
    const DEV = import.meta.env.DEV;

    // Request interceptor
    reqId = apiClient.interceptors.request.use(
        async (config) => {
            config.metadata = config.metadata || {};
            config.metadata.startTime = Date.now();
            const token = await getToken(authStore);
            if (token) {
                config.headers = config.headers || {};
                config.headers.Authorization = `Bearer ${token}`;
            }
            return config;
        },
        (error) => Promise.reject(error)
    );

    // Response interceptor
    resId = apiClient.interceptors.response.use(
        (response) => {
            if (DEV && response?.config?.metadata?.startTime) {
                const duration = Date.now() - response.config.metadata.startTime;
                console.log(
                    `[API] ${response.config.method?.toUpperCase()} ${response.config.url} ${response.status} - ${duration}ms`
                );
            }
            return response;
        },
        async (error) => {
            const config = error.config || {};

            if (DEV && config?.metadata?.startTime) {
                const duration = Date.now() - config.metadata.startTime;
                console.warn(
                    `[API] ${config.method?.toUpperCase?.()} ${config.url} error - ${duration}ms`, 
                    error?.response?.status
                );
            }

            if (apiClient.isCancel?.(error) || error.code === "ERR_CANCELED") {
                return Promise.reject(error);
            }

            if (!error.response) {
                if (!config._silent) {
                    if (error.code === "ECONNABORTED") {
                        toast(i18n.global.t("api_errors.timeout"), "warning");
                    } else if (
                        typeof navigator !== "undefined" &&
                        navigator.onLine === false
                    ) {
                        toast(i18n.global.t("api_errors.offline"), "warning");
                    } else {
                        toast(i18n.global.t("api_errors.network"));
                    }
                }
                return Promise.reject(error);
            }

            const { status, data } = error.response;
    
            if (status === 401 && !config._retry && !config._noRetry) {
                config._retry = true;
                try {
                    if (!refreshingPromise) {
                        refreshingPromise = supabase.auth
                            .refreshSession()
                            .finally(() => {
                                refreshingPromise = null;
                            });
                    }
                    const { data: refData, error: refErr } =
                        await refreshingPromise;

                    if (refErr || !refData?.session?.access_token) {
                        throw refErr || new Error("No session after refresh");
                    }

                    const newToken = refData.session.access_token;

                    config.headers = config.headers || {};
                    config.headers.Authorization = `Bearer ${newToken}`;

                    // Optionally sync store session if you don’t have onAuthStateChange in place
                    if ("session" in authStore)
                        authStore.session = refData.session;

                    return apiClient(config);
                    
                } catch (e) {
                    authStore?.signOutRedirectSignIn?.();
                    return Promise.reject(error);
                }
            }

            // Still 401 after refresh + retry (or retry disabled) → back to sign in
            if (status === 401) {
                authStore?.signOutRedirectSignIn?.();
                return Promise.reject(error);
            }

            switch (status) {
                case 403:
                    if (!config._silent)
                        toast(i18n.global.t("api_errors.forbidden"), "warning");
                    break;

                case 404:
                    if (!config._silent)
                        toast(i18n.global.t("api_errors.not_found"), "warning");
                    break;

                case 422: {
                    if (!config._silent) toast(apiErrorMessage(data), "negative", 5000);
                    break;
                }

                case 429: {
                    if (!config._silent) toast(i18n.global.t("api_errors.too_many_requests"), "warning", 5000);
                    break;
                }

                case 500:
                case 502:
                case 503:
                case 504: {
                    if (!config._silent) toast(apiErrorMessage(data, "server"), "negative", 5000);
                    break;
                }

                default: {
                    if (!config._silent) toast(apiErrorMessage(data));
                }
            }

            return Promise.reject(error);
        }
    );
};


// Global axios configuration
axios.defaults.validateStatus = function (status) {
    return status >= 200 && status < 300; // Accept 2xx status codes
};
