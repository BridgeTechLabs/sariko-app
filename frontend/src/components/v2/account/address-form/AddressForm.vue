<script>
import { mapState, mapActions } from 'pinia';
import { useAccountV2Store, toPhoneE164VN } from '@/stores/v2/account/accountStore';
import BaseChip from '@/components/v2/shared/BaseChip.vue';
import BaseTextField from '@/components/v2/shared/BaseTextField.vue';
import BaseSwitch from '@/components/v2/shared/BaseSwitch.vue';
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';
import apiAddress from '@/apis/address/apiAddress';

const LABELS = ['home', 'work', 'other']

export default {
    components: { BaseChip, BaseTextField, BaseSwitch, BaseIcon },

    data() {
        return {
            labels: LABELS,
            receiverTouched: false,
            phoneTouched: false,
            // Street search box — the address is only accepted once picked from Goong suggestions (needs lat/lon)
            streetQuery: '',
            suggestions: [],
            debounceTimer: null,
        }
    },

    computed: {
        ...mapState(useAccountV2Store, ['addressForm', 'addressFormSubmitted', 'isAddressReceiverValid', 'isAddressPhoneValid']),

        showReceiverError() {
            return (this.receiverTouched || this.addressFormSubmitted) && !this.isAddressReceiverValid
        },

        showPhoneError() {
            return (this.phoneTouched || this.addressFormSubmitted) && !this.isAddressPhoneValid
        },

        // Input shows the national part after the fixed +84 prefix; the store keeps E.164
        phoneNational: {
            get() {
                return this.addressForm.phone.replace(/^\+84/, '')
            },
            set(value) {
                this.addressForm.phone = toPhoneE164VN(value)
            },
        },
    },

    watch: {
        // Same component serves /new and /:id/edit — re-init whenever the route changes
        '$route.params.id': {
            handler: 'initFromRoute',
            immediate: true,
        },
    },

    beforeUnmount() {
        clearTimeout(this.debounceTimer)
    },

    methods: {
        ...mapActions(useAccountV2Store, ['initAddressForm', 'fetchAccount']),

        async initFromRoute(id) {
            this.receiverTouched = false
            this.phoneTouched = false
            this.suggestions = []
            let found = this.initAddressForm(id ?? null)

            // Opened directly / reloaded on the edit route — addresses aren't loaded yet, fetch then retry
            if (!found) {
                await this.fetchAccount()
                // Route changed while fetching — the watcher already re-ran for the new id
                if (this.$route.params.id !== id) return
                found = this.initAddressForm(id)
            }

            if (!found) {
                this.$router.replace({ name: 'account-addresses-v2' })
                return
            }
            this.streetQuery = this.addressForm.street
        },

        // Typing invalidates the picked address until a new suggestion is chosen
        onStreetInput(value) {
            this.streetQuery = value
            this.addressForm.street = ''
            this.addressForm.lat = null
            this.addressForm.lon = null

            clearTimeout(this.debounceTimer)
            if (value.trim().length < 3) {
                this.suggestions = []
                return
            }
            this.debounceTimer = setTimeout(() => this.fetchSuggestions(value), 350)
        },

        async fetchSuggestions(query) {
            try {
                const res = await apiAddress.search(query)
                // Drop stale responses when the user kept typing
                if (query !== this.streetQuery) return
                this.suggestions = res?.success ? res.results || [] : []
            } catch (error) {
                console.error(`AddressForm - fetchSuggestions - ${error}`)
            }
        },

        async onClickedSuggestion(item) {
            this.streetQuery = item.label
            this.suggestions = []
            try {
                const res = await apiAddress.getDetail(item.place_id)
                if (!res?.success) return
                this.addressForm.street = res.address || item.label
                this.addressForm.lat = res.lat
                this.addressForm.lon = res.lon
                this.streetQuery = this.addressForm.street
            } catch (error) {
                console.error(`AddressForm - onClickedSuggestion - ${error}`)
            }
        },
    },
}
</script>

<template>
    <div class="form">

        <div class="field">
            <p class="label">{{ $t('account_v2.address_form_save_as') }}</p>
            <div class="chips">
                <BaseChip
                    v-for="label in labels"
                    :key="label"
                    :selected="addressForm.label === label"
                    @click="addressForm.label = label"
                >
                    {{ $t(`account_v2.address_label_${label}`) }}
                </BaseChip>
            </div>
        </div>

        <div class="field">
            <BaseTextField
                :model-value="streetQuery"
                icon="map-pin"
                autocomplete="off"
                :label="$t('account_v2.address_form_street')"
                :placeholder="$t('account_v2.address_form_street_placeholder')"
                :hint="$t('account_v2.address_form_street_hint')"
                @update:model-value="onStreetInput"
            />
            <div v-if="suggestions.length" class="suggestions">
                <button
                    v-for="item in suggestions"
                    :key="item.place_id"
                    class="suggestion"
                    type="button"
                    @click="onClickedSuggestion(item)"
                >
                    <BaseIcon class="suggestion-icon" name="map-pin" :size="20" />
                    <span class="suggestion-texts">
                        <span class="suggestion-main">{{ item.main_text || item.label }}</span>
                        <span v-if="item.secondary_text" class="suggestion-sub">{{ item.secondary_text }}</span>
                    </span>
                </button>
            </div>
        </div>

        <BaseTextField
            v-model="addressForm.building"
            :label="$t('account_v2.address_form_building')"
            :label-note="$t('account_v2.address_form_optional')"
            :placeholder="$t('account_v2.address_form_building_placeholder')"
        />

        <BaseTextField
            v-model="addressForm.receiverName"
            autocomplete="name"
            :label="$t('account_v2.address_form_receiver')"
            :placeholder="$t('account_v2.address_form_receiver_placeholder')"
            :error="showReceiverError ? $t('account_v2.address_form_receiver_error') : null"
            @blur="receiverTouched = true"
        />

        <BaseTextField
            v-model="phoneNational"
            type="tel"
            inputmode="numeric"
            autocomplete="tel-national"
            prefix="+84"
            :label="$t('account_v2.address_form_phone')"
            :placeholder="$t('account_v2.address_form_phone_placeholder')"
            :error="showPhoneError ? $t('account_v2.address_form_phone_error') : null"
            @blur="phoneTouched = true"
        />

        <BaseTextField
            v-model="addressForm.note"
            multiline
            :label="$t('account_v2.address_form_note')"
            :label-note="$t('account_v2.address_form_optional')"
            :placeholder="$t('account_v2.address_form_note_placeholder')"
        />

        <div class="default-row">
            <p class="label">{{ $t('account_v2.address_form_set_default') }}</p>
            <BaseSwitch
                v-model="addressForm.isDefault"
                :size="26"
                :label="$t('account_v2.address_form_set_default')"
            />
        </div>

    </div>
</template>

<style scoped>
p {
    margin: 0;
}

.form {
    display: flex;
    flex-direction: column;
    gap: var(--space-24);
}

.field {
    display: flex;
    flex-direction: column;
    gap: var(--space-8);
}

.label {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.chips {
    display: flex;
    gap: var(--space-8);
}

.suggestions {
    display: flex;
    flex-direction: column;
    background: var(--card);
    border-radius: var(--radius-xl);
    box-shadow: 0 2px 8px color-mix(in srgb, var(--brand-navy) 5%, transparent);
    overflow: hidden;
}

.suggestion {
    display: flex;
    align-items: center;
    gap: var(--space-16);
    padding: var(--space-16);
    border: none;
    background: none;
    font-family: inherit;
    text-align: left;
    cursor: pointer;
}

.suggestion + .suggestion {
    border-top: var(--border-default) solid var(--border);
}

.suggestion-icon {
    flex-shrink: 0;
    color: var(--icon-muted);
}

.suggestion-texts {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
}

.suggestion-main {
    font-size: var(--font-size-base);
    line-height: var(--font-line-height-24);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
}

.suggestion-sub {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-secondary);
}

.default-row {
    display: flex;
    align-items: center;
    gap: var(--space-16);
}

.default-row .label {
    flex: 1;
}
</style>
