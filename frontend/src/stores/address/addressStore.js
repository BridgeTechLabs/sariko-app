import { defineStore } from 'pinia'
import apiAddress from '@/apis/address/apiAddress'
import apiUserAddresses from '@/apis/users/apiUserAddresses'
import apiUsers from '@/apis/users/apiUsers'
import { useAuthStore } from '@/stores/auth/authStore'

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

        // id null = a new address. Throws the API error for the form to show.
        async save(id, data) {
            await (id ? apiUserAddresses.update(id, data) : apiUserAddresses.create(data))
            await this.fetch()
        },

        // PATCH needs the location with any change (backend rule), so it goes along.
        async setDefault(address) {
            await apiUserAddresses.update(address.id, { address: address.address, lat: address.lat, lon: address.lon, is_default: true })
            await this.fetch()
        },

        async remove(id) {
            await apiUserAddresses.remove(id)
            await this.fetch()
        },

        syncDefault() {
            const d = this.addresses.find(a => a.is_default)
            const auth = useAuthStore()
            auth.inputAddress = d?.address || null
            auth.inputAddressDetails = d?.label || null
            auth.inputLat = d?.lat ?? null
            auth.inputLon = d?.lon ?? null
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
