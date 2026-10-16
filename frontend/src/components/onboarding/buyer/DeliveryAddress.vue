<script>
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapPin, LocateFixed, Search, X } from 'lucide-vue-next';
import { mapWritableState } from 'pinia';
import { useAuthStore } from '@/stores/auth/authStore';
import { apiClient } from '@/lib/axiosPolicy.js';

export default {
    components: { MapPin, LocateFixed, Search, X },

    data() {
        return {
            query: '',
            suggestions: [],
            isSearching: false,
            isLocating: false,
            showDropdown: false,
            _debounceTimer: null,
            _map: null,
            _marker: null,
        }
    },

    computed: {
        ...mapWritableState(useAuthStore, [
            'inputAddress',
            'inputAddressDetails',
            'inputLat',
            'inputLon',
        ])
    },

    mounted() {
        if (this.inputAddress) this.query = this.inputAddress
        if (this.inputLat && this.inputLon) {
            this.$nextTick(() => this.showMapAt(this.inputLat, this.inputLon))
        }
    },

    beforeUnmount() {
        if (this._map) { this._map.remove(); this._map = null }
        clearTimeout(this._debounceTimer)
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
                const res = await apiClient.get('/v1/address/search', { params: { q: this.query } })
                if (res.data?.success) {
                    this.suggestions = res.data.results || []
                    this.showDropdown = this.suggestions.length > 0
                }
            } catch (e) {
                console.error('Address search failed:', e)
            } finally {
                this.isSearching = false
            }
        },

        async selectSuggestion(item) {
            this.query = item.label || item.main_text
            this.showDropdown = false
            this.suggestions = []
            try {
                const res = await apiClient.get('/v1/address/detail', { params: { place_id: item.place_id } })
                if (res.data?.success) {
                    this.inputAddress = res.data.address || this.query
                    this.inputLat = res.data.lat
                    this.inputLon = res.data.lon
                    this.$nextTick(() => this.showMapAt(res.data.lat, res.data.lon))
                }
            } catch (e) {
                console.error('Place detail failed:', e)
                this.inputAddress = this.query
            }
        },

        clearSearch() {
            this.query = ''
            this.inputAddress = null
            this.inputLat = null
            this.inputLon = null
            this.suggestions = []
            this.showDropdown = false
        },

        async useCurrentLocation() {
            if (!navigator.geolocation) return
            this.isLocating = true
            navigator.geolocation.getCurrentPosition(
                async (pos) => {
                    const lat = pos.coords.latitude
                    const lon = pos.coords.longitude
                    this.inputLat = lat
                    this.inputLon = lon
                    try {
                        const res = await apiClient.get('/v1/address/reverse', { params: { lat, lon } })
                        if (res.data?.success && res.data.address) {
                            this.inputAddress = res.data.address
                            this.query = res.data.address
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
                attributionControl: false,
                dragging: false,
                scrollWheelZoom: false,
                doubleClickZoom: false,
                touchZoom: false,
            })
            L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                maxZoom: 19,
                subdomains: 'abcd'
            }).addTo(this._map)
            const icon = L.divIcon({
                className: '',
                html: `<div class="onboard-pin"></div>`,
                iconSize: [24, 24],
                iconAnchor: [12, 12],
            })
            this._marker = L.marker([lat, lon], { icon }).addTo(this._map)
        },
    }
}
</script>

<template>
    <div class="delivery-address">

        <div class="title-group">
            <div class="title">
                <MapPin class="icon-map-pin" :size="16" />
                {{ $t('onboarding_page.buyer.section_delivery_address.title') }}
            </div>
            <div class="optional">{{ $t('onboarding_page.buyer.section_delivery_address.label_optional') }}</div>
        </div>

        <!-- Search input -->
        <div class="search-wrap">
            <div class="search-box">
                <Search :size="15" class="icon-search" />
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
            <span>{{ isLocating ? 'Getting location...' : 'Use current location' }}</span>
        </button>

        <!-- Map preview (shown after address selected) -->
        <div v-show="inputAddress" class="map-preview">
            <div ref="mapContainer" class="map-container"></div>
        </div>

        <!-- Selected address preview -->
        <div v-if="inputAddress" class="address-preview">
            <MapPin :size="15" class="icon-pin" />
            <div class="address-text">{{ inputAddress }}</div>
        </div>

        <!-- Address details -->
        <div class="form-field">
            <q-input
                v-model="inputAddressDetails"
                dense outlined dark
                :placeholder="$t('onboarding_page.buyer.section_delivery_address.text_placeholder_address_details')"
            />
        </div>

    </div>
</template>

<style lang="scss" scoped>
.delivery-address {
    display: flex;
    flex-direction: column;
    gap: 12px;
    font-family: $sariko-font-family-secondary;
}

.title-group {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

.icon-map-pin {
    color: var(--color-accent);
}

.optional {
    background-color: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 0.75rem;
    font-size: 12px;
    color: var(--text-muted);
    padding: 2px 14px;
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
    height: 46px;
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
    font-family: $sariko-font-family-secondary;
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
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
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
    &:hover { background: rgba(255, 255, 255, 0.05); }
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

/* GPS button */
.btn-gps {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    padding: 11px 16px;
    background: var(--bg-surface);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    color: #fff;
    font-size: 14px;
    font-family: $sariko-font-family-secondary;
    cursor: pointer;

    &:hover:not(:disabled) { background: rgba(255, 255, 255, 0.08); }
    &:disabled { opacity: 0.6; cursor: not-allowed; }
}

.icon-locate { color: var(--color-accent); }

/* Map preview */
.map-preview {
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.map-container {
    width: 100%;
    height: 160px;
}

/* Selected address preview */
.address-preview {
    display: flex;
    gap: 10px;
    padding: 10px 14px;
    background: var(--bg-surface);
    border: 1px solid rgba(245, 166, 35, 0.3);
    border-radius: 12px;
}

.icon-pin {
    color: var(--color-accent);
    flex-shrink: 0;
    margin-top: 2px;
}

.address-text {
    font-size: 13px;
    color: var(--text-primary);
    line-height: 1.4;
    word-break: break-word;
}

/* Address details input */
.form-field {
    :deep(.q-field__native::placeholder) {
        color: var(--text-muted);
    }
}
</style>

<style>
.onboard-pin {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: #f5a623;
    border: 3px solid #fff;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
}
</style>
