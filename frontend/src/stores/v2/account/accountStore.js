import { defineStore } from 'pinia'
import apiUsers from '@/apis/users/apiUsers'
import apiUserAddresses from '@/apis/users/apiUserAddresses'
import apiAuth from '@/apis/auth/apiAuth'
import { i18n } from '@/plugins/i18n'
import { useAuthStore } from '@/stores/auth/authStore'
import { fileToBase64 } from '@/utils/fileToBase64'

// Address form keeps phone as E.164 (+84 + 9 digits). Accepts local "0903…", "84903…" or "+84903…" input
// and strips spaces/leading zeros so the field only ever holds the 9-digit national part.
export const toPhoneE164VN = (value) => {
    let digits = (value || '').replace(/\D/g, '')
    if (digits.length > 9 && digits.startsWith('84')) digits = digits.slice(2)
    digits = digits.replace(/^0+/, '')
    return digits ? `+84${digits}` : ''
}

// The country picker lists every country, but backend (to_e164_vn) + Lalamove only accept VN numbers for now
export const PHONE_SUPPORTED_COUNTRY = 'VN'

const isPhoneValidVN = (country, phone) => country === PHONE_SUPPORTED_COUNTRY && /^\+84\d{9}$/.test(phone)

const PASSWORD_MIN_LENGTH = 6

const AVATAR_MAX_BYTES = 2 * 1024 * 1024

const emptyProfileForm = () => ({
    name: '',
    phone: '',
    phoneCountry: PHONE_SUPPORTED_COUNTRY,
    avatarUrl: '',
})

const emptyPasswordForm = () => ({
    newPassword: '',
    confirmPassword: '',
})

const emptyAddressForm = () => ({
    label: null,
    street: '',
    lat: null,
    lon: null,
    building: '',
    receiverName: '',
    phone: '',
    phoneCountry: PHONE_SUPPORTED_COUNTRY,
    note: '',
    isDefault: false,
})

// `label` stores home/work/other; legacy rows (v1 put address_details there, "Home" when empty) fall back to 'other'
const toAddressV2 = (address) => {
    const raw = (address.label || '').trim().toLowerCase()
    return {
        id: address.id,
        label: ['home', 'work', 'other'].includes(raw) ? raw : 'other',
        receiverName: address.receiver_name,
        phone: address.phone_number,
        address: address.address,
        lat: address.lat,
        lon: address.lon,
        building: address.street_name || '',
        note: address.note || '',
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
            avatarUrl: '',
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
            orderUpdates: true,
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
        // Change password form draft — errors only show after Update is pressed
        passwordForm: emptyPasswordForm(),
        passwordFormSubmitted: false,
        // Set when a filled field loses focus — its error then shows live
        passwordNewTouched: false,
        passwordConfirmTouched: false,
        // Edit profile form draft — name/phone errors show after Save (phone also on blur once filled)
        profileForm: emptyProfileForm(),
        profileFormSubmitted: false,
        profilePhoneTouched: false,
        // Local object URL shown while the picked photo uploads
        avatarPreview: null,
        avatarUploading: false,
        // i18n key of the photo error (too big / not an image), replaces the "Tap to change photo" hint
        avatarErrorKey: null,
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

        isAddressPhoneValid: (state) => isPhoneValidVN(state.addressForm.phoneCountry, state.addressForm.phone),

        isAddressReceiverValid: (state) => state.addressForm.receiverName.trim() !== '',

        // Gates the Save button — receiver/phone errors are shown on Save instead of disabling it
        isAddressFormReady: (state) => {
            const form = state.addressForm
            return Boolean(form.label)
                && form.street.trim() !== ''
                && form.lat != null
                && form.lon != null
        },

        isPasswordLengthValid: (state) => state.passwordForm.newPassword.length >= PASSWORD_MIN_LENGTH,

        isPasswordConfirmValid: (state) => state.passwordForm.confirmPassword === state.passwordForm.newPassword,

        // Gates the Update button — length/mismatch errors are shown on Update instead of disabling it
        isPasswordFormReady: (state) => state.passwordForm.newPassword !== ''
            && state.passwordForm.confirmPassword !== '',

        isPasswordFormValid() {
            return this.isPasswordFormReady
                && this.isPasswordLengthValid
                && this.isPasswordConfirmValid
        },

        isProfileNameValid: (state) => state.profileForm.name.trim() !== '',

        isProfilePhoneValid: (state) => isPhoneValidVN(state.profileForm.phoneCountry, state.profileForm.phone),

        // Gates the Save button — nothing changed means nothing to save
        isProfileFormDirty: (state) => {
            const form = state.profileForm
            return form.name.trim() !== state.profile.name
                || form.phone !== toPhoneE164VN(state.profile.phone)
                || form.phoneCountry !== PHONE_SUPPORTED_COUNTRY
                || form.avatarUrl !== state.profile.avatarUrl
        },

        isProfileFormValid() {
            return this.isProfileNameValid && this.isProfilePhoneValid
        },

        isAddressFormValid() {
            return this.isAddressFormReady
                && this.isAddressReceiverValid
                && this.isAddressPhoneValid
        },
    },

    actions: {
        // Addresses come from GET /user_addresses (default first, then newest)
        async fetchAccount() {
            try {
                const [profileRes, addressRes] = await Promise.all([
                    apiUsers.getProfile(),
                    apiUserAddresses.list(),
                ])
                const user = profileRes?.user || {}
                this.profile = {
                    name: user.name || '',
                    phone: user.phone || '',
                    district: '',
                    avatarUrl: user.avatar_url || '',
                }
                this.selectedLanguage = toLanguageId(user.preferred_language)
                this.addresses = (addressRes?.addresses || []).map(toAddressV2)
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

        toggleNotification(key) {
            this.notifications[key] = !this.notifications[key]
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
                phoneCountry: PHONE_SUPPORTED_COUNTRY,
                note: address.note || '',
                isDefault: address.isDefault,
            }
            return true
        },

        // POST /user_addresses for a new address, PATCH /user_addresses/{id} when editing.
        // Backend makes the first address default and clears the old default when another is set.
        async saveAddressForm() {
            const form = this.addressForm
            const data = {
                label: form.label,
                address: form.street.trim(),
                street_name: form.building.trim() || null,
                lat: form.lat,
                lon: form.lon,
                receiver_name: form.receiverName.trim(),
                phone_number: form.phone,
                note: form.note.trim() || null,
            }

            if (this.editingAddressId === null) {
                await apiUserAddresses.create({ ...data, is_default: form.isDefault })
                return
            }
            // PATCH rejects is_default=false on the current default (400) — only send it when setting a new default
            await apiUserAddresses.update(this.editingAddressId, form.isDefault ? { ...data, is_default: true } : data)
        },

        // Fetches the profile first when opened directly (store not loaded yet)
        async initEditProfileForm() {
            this.profileForm = emptyProfileForm()
            this.profileFormSubmitted = false
            this.profilePhoneTouched = false
            this.avatarPreview = null
            this.avatarUploading = false
            this.avatarErrorKey = null

            if (!this.profile.name) await this.fetchAccount()
            this.profileForm = {
                name: this.profile.name,
                phone: toPhoneE164VN(this.profile.phone),
                phoneCountry: PHONE_SUPPORTED_COUNTRY,
                avatarUrl: this.profile.avatarUrl,
            }
        },

        // Uploads right away (POST /users/me/avatar); the returned URL is only saved to the profile on Save.
        // Throws on upload failure so the caller can show a toast.
        async uploadProfileAvatar(file) {
            this.avatarErrorKey = null
            if (!file.type.startsWith('image/')) {
                this.avatarErrorKey = 'account_v2.edit_profile_photo_type_error'
                return
            }
            if (file.size > AVATAR_MAX_BYTES) {
                this.avatarErrorKey = 'account_v2.edit_profile_photo_size_error'
                return
            }

            this.avatarPreview = URL.createObjectURL(file)
            this.avatarUploading = true
            try {
                const res = await apiUsers.uploadAvatar(await fileToBase64(file), file.type)
                this.profileForm.avatarUrl = res.avatar_url
            } catch (error) {
                this.avatarPreview = null
                throw error
            } finally {
                this.avatarUploading = false
            }
        },

        // PATCH /users/me/profile, then mirror the change into this store and authStore.user (v1 screens read it)
        async saveProfileForm() {
            const form = this.profileForm
            const res = await apiUsers.updateProfile({
                name: form.name.trim(),
                phone: form.phone,
                avatar_url: form.avatarUrl || null,
            })
            const user = res?.user || {}
            this.profile = {
                ...this.profile,
                name: user.name ?? form.name.trim(),
                phone: user.phone ?? form.phone,
                avatarUrl: form.avatarUrl,
            }

            const authStore = useAuthStore()
            if (authStore.user) {
                authStore.user.fullName = this.profile.name
                authStore.user.phone = this.profile.phone
                authStore.user.avatarUrl = this.profile.avatarUrl || null
            }
        },

        initPasswordForm() {
            this.passwordForm = emptyPasswordForm()
            this.passwordFormSubmitted = false
            this.passwordNewTouched = false
            this.passwordConfirmTouched = false
        },

        // Supabase auth updateUser — the session stays valid, so the form is just reset
        async changePassword() {
            await apiAuth.authUpdatePassword(this.passwordForm.newPassword)
            this.initPasswordForm()
        },
    },
})
