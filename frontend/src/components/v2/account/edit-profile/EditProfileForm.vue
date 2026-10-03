<script>
import { mapState, mapActions } from 'pinia';
import { useAccountV2Store, toPhoneE164VN, PHONE_SUPPORTED_COUNTRY } from '@/stores/v2/account/accountStore';
import BaseTextField from '@/components/v2/shared/BaseTextField.vue';
import BaseCountryCodeSelect from '@/components/v2/shared/BaseCountryCodeSelect.vue';

export default {
    components: { BaseTextField, BaseCountryCodeSelect },

    computed: {
        ...mapState(useAccountV2Store, [
            'profileForm', 'profileFormSubmitted', 'profilePhoneTouched',
            'isProfileNameValid', 'isProfilePhoneValid',
        ]),

        nameError() {
            return this.profileFormSubmitted && !this.isProfileNameValid
                ? this.$t('account_v2.edit_profile_name_error')
                : null
        },

        // Another country shows its error right away — only +84 can be saved for now
        phoneError() {
            if (this.profileForm.phoneCountry !== PHONE_SUPPORTED_COUNTRY) return this.$t('account_v2.phone_country_unsupported')
            return (this.profileFormSubmitted || this.profilePhoneTouched) && !this.isProfilePhoneValid
                ? this.$t('account_v2.edit_profile_phone_error')
                : null
        },

        // Same as the address form: input shows the national part after the country code; the store keeps E.164
        phoneNational: {
            get() {
                return this.profileForm.phone.replace(/^\+84/, '')
            },
            set(value) {
                this.profileForm.phone = toPhoneE164VN(value)
            },
        },
    },

    methods: {
        ...mapActions(useAccountV2Store, ['initEditProfileForm']),

        // Leaving the field empty doesn't count — no error before the user has typed anything
        onBlurPhone() {
            if (this.profileForm.phone) useAccountV2Store().profilePhoneTouched = true
        },
    },

    created() {
        this.initEditProfileForm()
    },
}
</script>

<template>
    <div class="edit-profile-form">
        <BaseTextField
            v-model="profileForm.name"
            size="lg"
            required
            autocomplete="name"
            :label="$t('account_v2.edit_profile_name')"
            :placeholder="$t('account_v2.edit_profile_name_placeholder')"
            :error="nameError"
        />

        <BaseTextField
            v-model="phoneNational"
            size="lg"
            required
            type="tel"
            inputmode="numeric"
            autocomplete="tel-national"
            :label="$t('account_v2.edit_profile_phone')"
            :placeholder="$t('account_v2.edit_profile_phone_placeholder')"
            :hint="$t('account_v2.edit_profile_phone_hint')"
            :error="phoneError"
            @blur="onBlurPhone"
        >
            <template #leading>
                <BaseCountryCodeSelect v-model="profileForm.phoneCountry" />
            </template>
        </BaseTextField>
    </div>
</template>

<style scoped>
.edit-profile-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-24);
}
</style>
