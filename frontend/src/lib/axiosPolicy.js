import axios from "axios";
import { useRouter } from "vue-router";
import { Notify } from "quasar";
import { useAuthStore } from "@/stores/auth/authStore.js";
import { supabase } from "@/lib/supabase";
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

function extractMessage(data) {
    if (!data) return null;
    if (typeof data === "string") return data;

    // FastAPI response messsage
    if (data.detail) {
        if (typeof data.detail === "string") return data.detail;
        if (Array.isArray(data.detail)) {
            // detail: [{ loc: [...], msg: '...', type: '...' }, ...]
            return data.detail
                .map((d) => {
                    if (typeof d === "string") return d;
                    const loc = Array.isArray(d.loc)
                        ? d.loc.slice(1).join(".")
                        : d.loc;
                    const msg = d.msg || d.message || "";
                    return loc ? `${loc}: ${msg}` : msg;
                })
                .filter(Boolean)
                .join(", ");
        }
        if (typeof data.detail === "object" && data.detail.message)
            return data.detail.message;
    }

    return data.message || data.error_description || data.error || null;
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
                        toast(
                            "Request timed out. Please try again.",
                            "warning"
                        );
                    } else if (
                        typeof navigator !== "undefined" &&
                        navigator.onLine === false
                    ) {
                        toast(
                            "You are offline. Please check your internet connection.",
                            "warning"
                        );
                    } else {
                        toast("Network error. Please check your connection.");
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
                        toast(
                            "You do not have permission to access this resource.",
                            "warning"
                        );
                    break;

                case 404:
                    if (!config._silent)
                        toast(
                            "The requested resource was not found.",
                            "warning"
                        );
                    break;

                case 422: {
                    const msg = extractMessage(data) || "Validation failed";
                    if (!config._silent) toast(msg, "negative", 5000);
                    break;
                }

                case 429: {
                    const msg =
                        extractMessage(data) ||
                        "Too many requests. Please try again later.";
                    if (!config._silent) toast(msg, "warning", 5000);
                    break;
                }

                case 500:
                case 502:
                case 503:
                case 504: {
                    const msg =
                        // extractMessage(data) || 
                        "Encountered an error. Please contact admin if the problem persists.";
                    if (!config._silent) toast(msg, "negative", 5000);
                    break;
                }

                default: {
                    const msg =
                        extractMessage(data) ||
                        `Request failed with status ${status}`;
                    if (!config._silent) toast(msg);
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
