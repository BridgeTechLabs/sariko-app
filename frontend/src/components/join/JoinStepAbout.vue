<script>
import { useJoinStore, NATIONALITIES } from '@/stores/join/joinStore'

export default {
    data() {
        return { nationalities: NATIONALITIES }
    },

    computed: {
        store() {
            return useJoinStore()
        },
        form() {
            return this.store.form
        },
        errors() {
            return this.store.visibleErrors(2)
        },
        idTypes() {
            return [
                { value: 'passport', label: this.$t('join_page.id_type_passport') },
                { value: 'cccd', label: this.$t('join_page.id_type_cccd') },
            ]
        },
        residentOptions() {
            return ['yes', 'no'].map(v => ({ value: v, label: this.$t(`join_page.resident_${v}`) }))
        },
    },

    methods: {
        err(field) {
            return this.errors[field] ? this.$t(this.errors[field], this.store.limits) : ''
        },
    },
}
</script>

<template>
    <div class="join-step">
        <div class="join-hint">{{ $t('join_page.about_hint') }}</div>

        <q-input v-model="form.full_name" dark outlined dense color="amber" :label="$t('join_page.label_full_name')" :hint="$t('join_page.hint_full_name')" :error="!!err('full_name')" :error-message="err('full_name')" maxlength="300" />
        <div class="join-grid">
            <q-input v-model="form.date_of_birth" dark outlined dense color="amber" stack-label type="date" :label="$t('join_page.label_date_of_birth')" :error="!!err('date_of_birth')" :error-message="err('date_of_birth')" />
            <q-select v-model="form.nationality" dark outlined dense color="amber" :options="nationalities" :label="$t('join_page.label_nationality')" />
            <q-input v-if="form.nationality === 'Other'" v-model="form.nationality_other" dark outlined dense color="amber" :label="$t('join_page.label_nationality_other')" :error="!!err('nationality_other')" :error-message="err('nationality_other')" maxlength="300" />
        </div>

        <div>
            <div class="join-label">{{ $t('join_page.label_id_type') }}</div>
            <q-option-group v-model="form.id_type" :options="idTypes" type="radio" inline dark color="amber" />
        </div>
        <div class="join-grid">
            <q-input v-model="form.id_number" dark outlined dense color="amber" :label="$t('join_page.label_id_number')" :error="!!err('id_number')" :error-message="err('id_number')" maxlength="300" />
            <q-input v-model="form.id_expiry_date" dark outlined dense color="amber" stack-label type="date" :label="$t('join_page.label_id_expiry')" :hint="form.id_type === 'passport' ? $t('join_page.hint_passport_validity', store.limits) : ''" :error="!!err('id_expiry_date')" :error-message="err('id_expiry_date')" />
        </div>

        <div class="join-section-title">{{ $t('join_page.section_contact') }}</div>
        <div class="join-grid">
            <q-input v-model="form.email" dark outlined dense color="amber" type="email" :label="$t('join_page.label_email')" :error="!!err('email')" :error-message="err('email')" maxlength="300" />
            <q-input v-model="form.phone" dark outlined dense color="amber" type="tel" :label="$t('join_page.label_phone')" :hint="$t('join_page.hint_phone')" :error="!!err('phone')" :error-message="err('phone')" maxlength="20" />
        </div>
        <q-input v-model="form.residential_address" dark outlined dense color="amber" :label="$t('join_page.label_residential_address')" :hint="$t('join_page.hint_residential_address')" :error="!!err('residential_address')" :error-message="err('residential_address')" maxlength="300" />

        <div class="join-section-title">{{ $t('join_page.section_tax') }}</div>
        <div class="join-grid">
            <q-input v-model="form.tax_code" dark outlined dense color="amber" :label="$t('join_page.label_tax_code')" :hint="$t('join_page.hint_optional')" maxlength="300" />
        </div>
        <div>
            <div class="join-label">{{ $t('join_page.label_tax_resident') }}</div>
            <div class="join-hint">{{ $t('join_page.hint_tax_resident') }}</div>
            <q-option-group v-model="form.tax_resident" :options="residentOptions" type="radio" inline dark color="amber" />
            <div v-if="err('tax_resident')" class="join-error">{{ err('tax_resident') }}</div>
        </div>
    </div>
</template>
