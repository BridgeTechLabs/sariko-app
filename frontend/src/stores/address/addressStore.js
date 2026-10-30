import { defineStore } from 'pinia'
import apiAddress from '@/apis/address/apiAddress'
import apiUserAddresses from '@/apis/users/apiUserAddresses'
import apiUsers from '@/apis/users/apiUsers'
import { useAuthStore } from '@/stores/auth/authStore'

// Label chips: Home / Office are stored as these words (older rows too), anything else is "Other".
export const LABEL_VALUES = { home: 'Home', office: 'Office' }
const LABEL_WORDS = { home: ['home', 'nhà'], office: ['office', 'work', 'công ty'] }

export function labelKind(label) {
    const word = (label || '').trim().toLowerCase()
    return Object.keys(LABEL_WORDS).find(k => LABEL_WORDS[k].includes(word)) || 'other'
}

// The buyer's delivery addresses (user_addresses) and the Goong lookups the address form uses.
// The default one is also kept in authStore.input*, which the cart and checkout read.
export const useAddressStore = defineStore('address', {
    state: () => ({
        addresses: [],      // default first, then newest (the API's order)
        loaded: false,
    }),

    getters: {
        byId: (state) => (id) => state.addresses.find(a => String(a.id) === String(id)) || null,
    },

    actions: {
        async fetch() {
            const res = await apiUserAddresses.list()
            this.addresses = res.addresses || []
            this.loaded = true
            this.syncDefault()
        },

        // id null = a new address. Returns the saved row; throws the API error for the form to show.
        async save(id, data) {
            const res = await (id ? apiUserAddresses.update(id, data) : apiUserAddresses.create(data))
            await this.fetch()
            return res.address
        },

        async remove(id) {
            await apiUserAddresses.remove(id)
            await this.fetch()
        },

        syncDefault() {
            this.useForOrder(this.addresses.find(a => a.is_default))
        },

        // The address the next order goes to (cart / checkout read authStore.input*). Picking one in
        // the cart does not change the default.
        useForOrder(a) {
            const auth = useAuthStore()
            auth.inputAddress = a?.address || null
            auth.inputAddressDetails = a?.label || null
            auth.inputLat = a?.lat ?? null
            auth.inputLon = a?.lon ?? null
            auth.inputReceiverName = a?.receiver_name || null
            auth.inputReceiverPhone = a?.phone_number || null
            auth.inputDeliveryNote = [a?.street_name, a?.note].filter(Boolean).join(' · ') || null
        },

        // Seller: the store's pickup address lives in seller_profiles.
        async saveStoreAddress(data) {
            await apiUsers.updateProfile(data)
        },

        async search(q) {
            const res = await apiAddress.search(q)
            return res?.success ? res.results || [] : []
        },

        async placeDetail(placeId) {
            const res = await apiAddress.getDetail(placeId)
            return res?.success ? res : null
        },

        async reverse(lat, lon) {
            const res = await apiAddress.reverse(lat, lon)
            return res?.success ? res.address : null
        },
    },
})
