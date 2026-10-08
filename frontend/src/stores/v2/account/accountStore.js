import { defineStore } from 'pinia'
import { Notify } from 'quasar'
import apiUsers from '@/apis/users/apiUsers'
import { i18n } from '@/plugins/i18n'
import { enablePush, disablePush, getPushSubscription } from '@/composables/pushNotifications'

// Address form keeps phone as E.164 (+84 + 9 digits). Accepts local "0903…", "84903…" or "+84903…" input
// and strips spaces/leading zeros so the field only ever holds the 9-digit national part.
export const toPhoneE164VN = (value) => {
    let digits = (value || '').replace(/\D/g, '')
    if (digits.length > 9 && digits.startsWith('84')) digits = digits.slice(2)
    digits = digits.replace(/^0+/, '')
    return digits ? `+84${digits}` : ''
}

const emptyAddressForm = () => ({
    label: null,
    street: '',
    lat: null,
    lon: null,
    building: '',
    receiverName: '',
    phone: '',
    note: '',
    isDefault: false,
})

// Backend stores address_details in `label` ("Home" when empty) — map it onto the v2 label set
const toAddressV2 = (address, profile) => {
    const raw = (address.label || '').trim()
    const label = ['home', 'work'].includes(raw.toLowerCase()) ? raw.toLowerCase() : 'other'
    return {
        id: address.id,
        label,
        receiverName: profile.name,
        phone: profile.phone,
        address: address.address,
        lat: address.lat,
        lon: address.lon,
        building: label === 'other' ? raw : '',
        isDefault: address.is_default,
    }
}

// Language screen options. `locale` is the i18n locale applied (no Tagalog translation → en_ph).
// `backendValue` is what users.preferred_language stores — 'Fillipino' (sic) matches onboarding + authStore LANG_MAP.
export const LANGUAGE_OPTIONS_V2 = [
    { id: 'en', code: 'EN', locale: 'en_ph', backendValue: 'English' },
    { id: 'tl', code: 'TL', locale: 'en_ph', backendValue: 'Fillipino' },
    { id: 'vi', code: 'VI', locale: 'vi', backendValue: 'Tiếng Việt' },
]

// Unknown/empty preferred_language → derive from the active locale
const toLanguageId = (preferredLanguage) =>
    LANGUAGE_OPTIONS_V2.find(o => o.backendValue === preferredLanguage)?.id
    ?? (i18n.global.locale === 'vi' ? 'vi' : 'en')

// profile + addresses come from the API (fetchAccount); the rest is still mock data
export const useAccountV2Store = defineStore('accountV2Store', {
    state: () => ({
        profile: {
            name: '',
            phone: '',
            district: '',
        },
        stats: {
            orders: 12,
            reviews: 5,
            following: 8,
        },
        addresses: [],
        deliveryFeeEstimate: 12000,
        defaultPayment: 'VNPay',
        notifications: {
            // Mirrors this device's push subscription — set by syncPushState(), not a saved preference
            orderUpdates: false,
            sellerNews: false,
        },
        foundingSlotsLeft: 7,
        // Language screen selection — id from LANGUAGE_OPTIONS_V2, synced from preferred_language in fetchAccount
        selectedLanguage: toLanguageId(null),
        // Add / edit address form draft — editingAddressId null means "new"
        editingAddressId: null,
        addressForm: emptyAddressForm(),
        // Set when Save is pressed — shows every field error, not only the touched ones
        addressFormSubmitted: false,
    }),

    getters: {
        savedAddressCount: (state) => state.addresses.length,

        initials: (state) => state.profile.name
            .split(' ')
            .map(word => word[0])
            .join('')
            .slice(0, 2)
            .toUpperCase(),

        isEditingAddress: (state) => state.editingAddressId !== null,

        isAddressPhoneValid: (state) => /^\+84\d{9}$/.test(state.addressForm.phone),

        isAddressReceiverValid: (state) => state.addressForm.receiverName.trim() !== '',

        // Gates the Save button — receiver/phone errors are shown on Save instead of disabling it
        isAddressFormReady: (state) => {
            const form = state.addressForm
            return Boolean(form.label)
                && form.street.trim() !== ''
                && form.lat != null
                && form.lon != null
        },

        isAddressFormValid() {
            return this.isAddressFormReady
                && this.isAddressReceiverValid
                && this.isAddressPhoneValid
        },
    },

    actions: {
        // Backend only exposes the default address (GET /users/me/address), so the list has at most one item
        async fetchAccount() {
            try {
                const [profileRes, addressRes] = await Promise.all([
                    apiUsers.getProfile(),
                    apiUsers.getDefaultAddress(),
                ])
                const user = profileRes?.user || {}
                this.profile = {
                    name: user.name || '',
                    phone: user.phone || '',
                    district: '',
                }
                this.selectedLanguage = toLanguageId(user.preferred_language)
                this.addresses = addressRes?.address ? [toAddressV2(addressRes.address, this.profile)] : []
            } catch (error) {
                console.error(`accountV2Store - fetchAccount - ${error}`)
            }
        },

        // Applies the locale right away, then persists via PATCH /users/me/profile.
        // A failed PATCH keeps the local change (axiosPolicy already shows the error toast).
        async selectLanguage(id) {
            const option = LANGUAGE_OPTIONS_V2.find(o => o.id === id)
            if (!option || id === this.selectedLanguage) return

            this.selectedLanguage = id
            i18n.global.locale = option.locale
            localStorage.setItem('lang', option.locale)

            try {
                await apiUsers.updateProfile({ preferred_language: option.backendValue })
            } catch (error) {
                console.warn(`accountV2Store - selectLanguage - ${error}`)
            }
        },

        async toggleNotification(key) {
            if (key === 'orderUpdates') return this.togglePush()
            this.notifications[key] = !this.notifications[key]
        },

        async syncPushState() {
            this.notifications.orderUpdates = !!(await getPushSubscription())
        },

        async togglePush() {
            try {
                if (this.notifications.orderUpdates) {
                    await disablePush()
                    this.notifications.orderUpdates = false
                    return
                }
                const result = await enablePush()
                this.notifications.orderUpdates = result === 'enabled'
                if (result !== 'enabled') {
                    Notify.create({
                        classes: 'quasar-notify-negative',
                        message: i18n.global.t(`account_v2.push_${result}`),
                        progress: true,
                        position: 'bottom',
                    })
                }
            } catch (error) {
                console.warn(`accountV2Store - togglePush - ${error}`)
            }
        },

        // Returns false when the id doesn't match a saved address
        initAddressForm(id = null) {
            this.editingAddressId = null
            this.addressForm = emptyAddressForm()
            this.addressFormSubmitted = false
            if (id === null) return true

            // Route params are strings, API ids are numbers (bigint)
            const address = this.addresses.find(a => String(a.id) === String(id))
            if (!address) return false

            this.editingAddressId = id
            this.addressForm = {
                label: address.label,
                street: address.address,
                lat: address.lat,
                lon: address.lon,
                building: address.building || '',
                receiverName: address.receiverName,
                phone: toPhoneE164VN(address.phone),
                note: address.note || '',
                isDefault: address.isDefault,
            }
            return true
        },

        // Backend keeps a single default address (PATCH /users/me/profile upserts it) — same payload as v1 AddressForm.
        // receiverName / phone / note / label / isDefault have no column yet, so they are not sent.
        async saveAddressForm() {
            const form = this.addressForm
            await apiUsers.updateProfile({
                address: form.street.trim(),
                address_details: form.building.trim() || null,
                lat: form.lat,
                lon: form.lon,
            })
        },
    },
})
