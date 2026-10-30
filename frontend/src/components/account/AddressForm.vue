<script>
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { addOsmTiles } from '@/utils/mapTiles';
import { MapPin, LocateFixed, Search, X } from 'lucide-vue-next';
import { useAuthStore } from '@/stores/auth/authStore';
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import { useAddressStore } from '@/stores/address/addressStore';

export default {
    components: { MapPin, LocateFixed, Search, X },

    // Seller: the store's pickup address. Buyer: one delivery address (addressId 'new' = add one).
    // embedded: inside another page (seller profile form): emit "saved" instead of leaving.
    props: {
        embedded: { type: Boolean, default: false },
        addressId: { type: String, default: 'new' },
    },
    emits: ['saved'],

    data() {
        return {
            query: '',
            suggestions: [],
            isSearching: false,
            isLocating: false,
            saving: false,
            showDropdown: false,
            address: '',
            addressDetails: '',
            lat: null,
            lon: null,
            // buyer only
            receiverName: '',
            phone: '',
            label: '',
            note: '',
            isDefault: false,
            makeDefault: false,
            _debounceTimer: null,
            _map: null,
            _marker: null,
        }
    },

    computed: {
        authStore() {
            return useAuthStore()
        },
        // Sellers edit the store pickup address (seller_profiles), not a buyer delivery address.
        isSeller() {
            return !!this.authStore.user?.isSeller
        },
        addressStore() {
            return useAddressStore()
        },
        isNew() {
            return this.addressId === 'new'
        },
        canSave() {
            const buyerFields = this.isSeller || (this.lat !== null && this.receiverName.trim() && this.phone.trim())
            return !!this.address && !!buyerFields && !this.saving
        }
    },

    async mounted() {
        if (this.isSeller) {
            const dashboardStore = useDashboardStore()
            await dashboardStore.fetchSellerInfo()
            const info = dashboardStore.sellerInfo || {}
            this.address = info.address || ''
            this.lat = info.lat || null
            this.lon = info.lon || null
        } else {
            if (!this.addressStore.loaded) await this.addressStore.fetch()
            const row = this.isNew ? null : this.addressStore.byId(this.addressId)
            if (!this.isNew && !row) return this.$router.replace('/account/address')
            this.address = row?.address || ''
            this.addressDetails = row?.street_name || ''
            this.lat = row?.lat ?? null
            this.lon = row?.lon ?? null
            this.receiverName = row?.receiver_name || this.authStore.user?.fullName || ''
            this.phone = row?.phone_number || this.authStore.user?.phone || ''
            this.label = row?.label || ''
            this.note = row?.note || ''
            this.isDefault = !!row?.is_default
        }
        if (this.address) this.query = this.address
        if (this.lat && this.lon) {
            this.$nextTick(() => this.showMapAt(this.lat, this.lon))
        }
    },

    beforeUnmount() {
        if (this._map) { this._map.remove(); this._map = null }
    },

    methods: {
        onQueryInput() {
            clearTimeout(this._debounceTimer)
            if (!this.query.trim() || this.query.length < 3) {
                this.suggestions = []
                this.showDropdown = false
                return
            }
            this._debounceTimer = setTimeout(() => this.fetchSuggestions(), 350)
        },

        async fetchSuggestions() {
            this.isSearching = true
            try {
                this.suggestions = await this.addressStore.search(this.query)
                this.showDropdown = this.suggestions.length > 0
            } catch (e) {
                console.error('Address search failed:', e)
            } finally {
                this.isSearching = false
            }
        },

        async selectSuggestion(item) {
            this.query = item.label
            this.showDropdown = false
            this.suggestions = []

            // Fetch lat/lon from place detail
            try {
                const place = await this.addressStore.placeDetail(item.place_id)
                if (place) {
                    this.address = place.address || item.label
                    this.lat = place.lat
                    this.lon = place.lon
                    this.$nextTick(() => this.showMapAt(place.lat, place.lon))
                }
            } catch (e) {
                console.error('Place detail failed:', e)
                // Fallback: use label without coords
                this.address = item.label
            }
        },

        clearSearch() {
            this.query = ''
            this.address = ''
            this.lat = null
            this.lon = null
            this.suggestions = []
            this.showDropdown = false
        },

        showMapAt(lat, lon) {
            if (!this.$refs.mapContainer) return
            if (this._map) {
                this._map.setView([lat, lon], 16)
                this._marker.setLatLng([lat, lon])
                return
            }
            this._map = L.map(this.$refs.mapContainer, {
                center: [lat, lon],
                zoom: 16,
                zoomControl: false,
                dragging: false,
                scrollWheelZoom: false,
                doubleClickZoom: false,
                touchZoom: false,
            })
            addOsmTiles(this._map)
            const icon = L.divIcon({
                className: '',
                html: `<div class="preview-pin"></div>`,
                iconSize: [24, 24],
                iconAnchor: [12, 12],
            })
            this._marker = L.marker([lat, lon], { icon }).addTo(this._map)
        },

        async useCurrentLocation() {
            if (!navigator.geolocation) return
            this.isLocating = true
            navigator.geolocation.getCurrentPosition(
                async (pos) => {
                    const lat = pos.coords.latitude
                    const lon = pos.coords.longitude
                    this.lat = lat
                    this.lon = lon
                    try {
                        const found = await this.addressStore.reverse(lat, lon)
                        if (found) {
                            this.address = found
                            this.query = found
                        }
                    } catch (e) {
                        console.error('Reverse geocode failed:', e)
                    }
                    this.$nextTick(() => this.showMapAt(lat, lon))
                    this.isLocating = false
                },
                (err) => {
                    console.error('Geolocation error:', err)
                    this.isLocating = false
                },
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
            )
        },

        async onSave() {
            if (!this.canSave) return
            this.saving = true
            try {
                if (this.isSeller) {
                    await this.addressStore.saveStoreAddress({ address: this.address, lat: this.lat, lon: this.lon })
                    await useDashboardStore().fetchSellerInfo()
                } else {
                    await this.addressStore.save(this.isNew ? null : this.addressId, {
                        address: this.address, lat: this.lat, lon: this.lon,
                        street_name: this.addressDetails.trim() || null,
                        receiver_name: this.receiverName.trim(), phone_number: this.phone.trim(),
                        label: this.label.trim() || null, note: this.note.trim() || null,
                        ...(this.isNew ? { is_default: this.makeDefault } : {}),
                    })
                }
                this.$q.notify({
                    classes: 'quasar-notify-positive',
                    message: `✔️ ${this.$t('common.toast_update_success')}`,
                    position: 'bottom',
                    timeout: 1500,
                })
                if (this.embedded) this.$emit('saved')
                else this.$router.push(this.isSeller ? '/account' : '/account/address')
            } catch (e) {
                this.notifyFailed(e?.response?.data?.detail === 'Invalid phone number' ? 'delivery_address_page.error_phone' : 'common.toast_update_failed')
            } finally {
                this.saving = false
            }
        },

        notifyFailed(key) {
            this.$q.notify({ classes: 'quasar-notify-negative', message: this.$t(key), position: 'bottom', timeout: 2000 })
        },

        async onSetDefault() {
            this.saving = true
            try {
                await this.addressStore.setDefault(this.addressStore.byId(this.addressId))
                this.isDefault = true
            } catch (e) {
                this.notifyFailed('common.toast_update_failed')
            } finally {
                this.saving = false
            }
        },

        onDelete() {
            this.$q.dialog({
                title: this.$t('delivery_address_page.delete_title'),
                message: this.$t('delivery_address_page.delete_message'),
                ok: { label: this.$t('delivery_address_page.button_delete'), color: 'negative', noCaps: true, unelevated: true },
                cancel: { label: this.$t('common.button_label_cancel'), flat: true, noCaps: true },
                dark: true,
            }).onOk(async () => {
                this.saving = true
                try {
                    await this.addressStore.remove(this.addressId)
                    this.$router.push('/account/address')
                } catch (e) {
                    this.notifyFailed('common.toast_update_failed')
                } finally {
                    this.saving = false
                }
            })
        },
    }
}
</script>

<template>
    <div class="address-form">

        <!-- Receiver (buyers only) -->
        <template v-if="!isSeller">
            <div class="form-field">
                <label class="field-label">{{ $t('delivery_address_page.label_receiver') }}</label>
                <q-input v-model="receiverName" dense outlined dark maxlength="100" />
            </div>
            <div class="form-field">
                <label class="field-label">{{ $t('delivery_address_page.label_phone') }}</label>
                <q-input v-model="phone" dense outlined dark type="tel" maxlength="20" />
            </div>
        </template>

        <!-- Search input -->
        <div class="search-wrap">
            <div class="search-box">
                <Search :size="16" class="icon-search" />
                <input
                    v-model="query"
                    class="search-input"
                    :placeholder="$t('delivery_address_page.search_placeholder')"
                    autocomplete="off"
                    @input="onQueryInput"
                    @focus="showDropdown = suggestions.length > 0"
                />
                <button v-if="query" class="btn-clear" @click="clearSearch">
                    <X :size="14" />
                </button>
                <q-spinner-dots v-if="isSearching" color="accent" size="16px" class="spinner" />
            </div>

            <!-- Dropdown suggestions -->
            <div v-if="showDropdown" class="dropdown">
                <button
                    v-for="(item, i) in suggestions"
                    :key="i"
                    class="suggestion-item"
                    @click="selectSuggestion(item)"
                >
                    <MapPin :size="14" class="icon-pin-sm" />
                    <div class="suggestion-content">
                        <span class="suggestion-main">{{ item.main_text || item.label }}</span>
                        <span v-if="item.secondary_text" class="suggestion-sub">{{ item.secondary_text }}</span>
                    </div>
                </button>
            </div>
        </div>

        <!-- GPS button -->
        <button class="btn-gps" :disabled="isLocating" @click="useCurrentLocation">
            <q-spinner-dots v-if="isLocating" color="accent" size="18px" />
            <LocateFixed v-else :size="18" class="icon-locate" />
            <span>{{ isLocating
                ? $t('delivery_address_page.button_locating')
                : $t('delivery_address_page.button_use_current_location') }}</span>
        </button>

        <!-- Map preview (shown after address selected) -->
        <div v-show="address" class="map-preview">
            <div ref="mapContainer" class="map-container"></div>
        </div>

        <!-- Selected address preview -->
        <div v-if="address" class="address-preview">
            <MapPin :size="16" class="icon-pin" />
            <div class="address-text">{{ address }}</div>
        </div>

        <!-- Street, note, label (buyers only: seller_profiles has no column for them) -->
        <template v-if="!isSeller">
            <div class="form-field">
                <label class="field-label">{{ $t('delivery_address_page.label_street') }}</label>
                <q-input v-model="addressDetails" dense outlined dark :placeholder="$t('delivery_address_page.placeholder_street')" />
            </div>
            <div class="form-field">
                <label class="field-label">{{ $t('delivery_address_page.label_note') }}</label>
                <q-input v-model="note" dense outlined dark :placeholder="$t('delivery_address_page.placeholder_note')" />
            </div>
            <div class="form-field">
                <label class="field-label">{{ $t('delivery_address_page.label_label') }}</label>
                <q-input v-model="label" dense outlined dark maxlength="50" :placeholder="$t('delivery_address_page.placeholder_label')" />
            </div>
            <q-checkbox v-if="isNew && addressStore.addresses.length" v-model="makeDefault" dark color="amber" :label="$t('delivery_address_page.button_set_default')" />
        </template>

        <!-- Save -->
        <q-btn
            class="btn-save"
            no-caps unelevated
            :disable="!canSave"
            :loading="saving"
            @click="onSave"
        >
            {{ saving ? $t('common.button_label_saving') : $t('delivery_address_page.button_save') }}
        </q-btn>

        <template v-if="!isSeller && !isNew">
            <q-btn v-if="!isDefault" class="btn-secondary" no-caps outline :disable="saving" :label="$t('delivery_address_page.button_set_default')" @click="onSetDefault" />
            <q-btn class="btn-delete" no-caps flat :disable="saving" :label="$t('delivery_address_page.button_delete')" @click="onDelete" />
        </template>

    </div>
</template>

<style lang="scss" scoped>
.address-form {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

/* Search */
.search-wrap {
    position: relative;
}

.search-box {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 14px;
    background: var(--bg-surface);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    height: 48px;
}

.icon-search {
    color: var(--text-secondary);
    flex-shrink: 0;
}

.search-input {
    flex: 1;
    background: none;
    border: none;
    outline: none;
    color: var(--text-primary);
    font-size: 14px;
    min-width: 0;

    &::placeholder {
        color: var(--text-secondary);
    }
}

.btn-clear {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    display: flex;
    align-items: center;
    padding: 0;
    flex-shrink: 0;
}

.spinner {
    flex-shrink: 0;
}

/* Dropdown */
.dropdown {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    right: 0;
    background: #1f2940;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    overflow: hidden;
    z-index: 100;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}

.suggestion-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    width: 100%;
    padding: 12px 14px;
    background: none;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    cursor: pointer;
    text-align: left;

    &:last-child { border-bottom: none; }
    &:hover { background: rgba(255,255,255,0.05); }
}

.icon-pin-sm {
    color: var(--color-accent);
    flex-shrink: 0;
    margin-top: 2px;
}

.suggestion-content {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
}

.suggestion-main {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    line-height: 1.3;
}

.suggestion-sub {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* Map preview */
.map-preview {
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.1);
}

.map-container {
    width: 100%;
    height: 180px;
}

/* GPS button */
.btn-gps {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    padding: 12px 16px;
    background: var(--bg-surface);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    color: #fff;
    font-size: 14px;
    cursor: pointer;

    &:hover:not(:disabled) { background: rgba(255,255,255,0.08); }
    &:disabled { opacity: 0.6; cursor: not-allowed; }
}

.icon-locate { color: var(--color-accent); }

/* Selected preview */
.address-preview {
    display: flex;
    gap: 10px;
    padding: 12px 14px;
    background: var(--bg-surface);
    border: 1px solid rgba(245, 166, 35, 0.3);
    border-radius: 12px;
}

.icon-pin { color: var(--color-accent); flex-shrink: 0; margin-top: 2px; }

.address-text {
    font-size: 13px;
    color: var(--text-primary);
    line-height: 1.4;
}

/* Form */
.form-field {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.field-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    padding-left: 4px;
}

.btn-save {
    margin-top: 8px;
    padding: 14px;
    background: var(--color-accent, #f5A623);
    color: #121b2f;
    font-weight: 700;
    font-size: 15px;
    border-radius: 12px;
}

.btn-secondary {
    padding: 12px;
    color: var(--color-accent, #f5A623);
    font-weight: 600;
    border-radius: 12px;
}

.btn-delete {
    padding: 12px;
    color: var(--color-error, #ef4444);
    font-weight: 600;
}
</style>

<style>
.preview-pin {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: #f5a623;
    border: 3px solid #fff;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
}
</style>
