<script>
import { mapState, mapActions } from 'pinia'
import { useProfileCompletionStore } from '@/stores/seller/profileCompletionStore'
import { BANKS, NATIONALITIES } from '@/stores/join/joinStore'
import AddressForm from '@/components/account/AddressForm.vue'

// Backend error code -> [field, i18n key]. Field '' = message above the Save button.
const ERRORS = {
    under_age: ['date_of_birth', 'join_page.error_age'],
    invalid_id_type: ['id_type', 'join_page.error_required'],
    invalid_id_number: ['id_number', 'seller_profile.error_id_number'],
    id_expiry_required: ['id_expiry_date', 'join_page.error_required'],
    id_expired: ['id_expiry_date', 'seller_profile.error_id_expired'],
    id_expiring: ['id_expiry_date', 'seller_profile.error_id_expiring'],
    invalid_email: ['email', 'join_page.error_email'],
    invalid_bank_account: ['bank_account_number', 'join_page.error_account_number'],
    bank_holder_mismatch: ['bank_account_holder', 'seller_profile.error_bank_holder'],
    invalid_phone: ['phone', 'join_page.error_phone'],
    agreement_required: ['agreed', 'seller_profile.error_agree'],
    consent_required: ['agreed', 'seller_profile.error_agree'],
    signature_mismatch: ['signature_name', 'join_page.error_signature'],
    agreement_outdated: ['', 'seller_profile.error_outdated'],
    missing_group: ['', 'seller_profile.error_missing_group'],
    invalid_location: ['', 'seller_profile.error_location'],
    file_too_large: ['id_document', 'join_page.error_file_size'],
    invalid_file_type: ['id_document', 'join_page.error_file_type'],
    too_many_files: ['id_document', 'join_page.error_too_many_files'],
}

export default {
    name: 'ProfileCompletionForm',

    components: { AddressForm },

    data() {
        return {
            banks: BANKS,
            nationalities: NATIONALITIES,
            shown: [],          // cards to show: the groups missing when the page opened
            form: null,
            idFile: null,       // passport photo, sent right after the identity is saved
            errors: {},
            saving: false,
        }
    },

    computed: {
        ...mapState(useProfileCompletionStore, ['data', 'missing', 'loading']),
        limits() {
            return this.data?.limits || {}
        },
        prefill() {
            return this.data?.prefill || {}
        },
        idTypes() {
            return [
                { value: 'cccd', label: this.$t('join_page.id_type_cccd') },
                { value: 'passport', label: this.$t('join_page.id_type_passport') },
            ]
        },
        residentOptions() {
            return ['yes', 'no'].map(v => ({ value: v, label: this.$t(`join_page.resident_${v}`) }))
        },
        // A passport photo is needed when the seller picks passport, or saved one without a photo.
        needsPassportPhoto() {
            return (this.has('identity') && this.form.id_type === 'passport') || this.missing.includes('id_document')
        },
        fullName() {
            const first = this.form.first_name || this.prefill.first_name
            const last = this.form.last_name || this.prefill.last_name
            return [first, last].filter(Boolean).join(' ')
        },
        // The pickup address is saved by its own form above; the rest goes in one request.
        waitingForAddress() {
            return this.has('pickup_address') && this.missing.includes('pickup_address')
        },
        canSave() {
            return !this.saving && !this.waitingForAddress && (this.payloadGroups.length > 0 || this.idFile)
        },
        payloadGroups() {
            return this.shown.filter(g => !['pickup_address', 'id_document'].includes(g))
        },
    },

    methods: {
        ...mapActions(useProfileCompletionStore, ['fetch', 'save', 'uploadIdDocument']),

        has(group) {
            return this.shown.includes(group)
        },

        err(field) {
            return this.errors[field] || ''
        },

        initForm() {
            const p = this.prefill
            const knownNationality = !p.nationality || NATIONALITIES.includes(p.nationality)
            const knownBank = !p.bank_name || BANKS.includes(p.bank_name)
            this.form = {
                first_name: p.first_name, last_name: p.last_name, date_of_birth: p.date_of_birth || '',
                nationality: knownNationality ? p.nationality : 'Other', nationality_other: knownNationality ? '' : p.nationality,
                id_type: p.id_type || 'cccd', id_number: '', id_expiry_date: p.id_expiry_date || '',
                residential_address: p.residential_address, email: p.email,
                tax_resident: p.tax_resident === true ? 'yes' : p.tax_resident === false ? 'no' : null, tax_code: p.tax_code,
                bank_name: knownBank ? p.bank_name : 'Other', bank_name_other: knownBank ? '' : p.bank_name,
                bank_account_number: '', bank_account_holder: p.bank_account_holder,
                phone: p.phone,
                agree_accurate: false, agree_data: false, agree_agreement: false, signature_name: '',
            }
        },

        payload() {
            const f = this.form
            const body = {}
            if (this.has('identity')) {
                body.identity = {
                    first_name: f.first_name, last_name: f.last_name, date_of_birth: f.date_of_birth || null,
                    nationality: f.nationality === 'Other' ? f.nationality_other : f.nationality,
                    id_type: f.id_type, id_number: f.id_number, id_expiry_date: f.id_expiry_date || null,
                    residential_address: f.residential_address, email: f.email,
                }
            }
            if (this.has('tax')) {
                body.tax = { tax_resident: f.tax_resident ? f.tax_resident === 'yes' : null, tax_code: f.tax_code }
            }
            if (this.has('bank')) {
                body.bank = {
                    bank_name: f.bank_name === 'Other' ? f.bank_name_other : f.bank_name,
                    bank_account_number: f.bank_account_number, bank_account_holder: f.bank_account_holder,
                }
            }
            if (this.has('phone')) body.phone = f.phone
            if (this.has('agreement')) {
                body.agreement = {
                    agreed: f.agree_accurate && f.agree_agreement, personal_data_consent: f.agree_data,
                    agreement_version: this.data.agreement_version_current, signature_name: f.signature_name,
                }
            }
            return body
        },

        showError(e) {
            const d = e?.response?.data?.detail
            const [field, key] = ERRORS[d?.code] || ['', 'seller_profile.error_save']
            const params = {
                ...this.limits, ...d,
                minAge: this.limits.min_age, mb: this.limits.max_file_mb, maxFiles: this.limits.max_files_per_kind,
                items: (d?.groups || []).map(g => this.$t(`seller_profile.group_${g}`)).join(', '),
            }
            this.errors = { [d?.code === 'missing_field' ? d.field : field]: this.$t(d?.code === 'missing_field' ? 'join_page.error_required' : key, params) }
        },

        async onSave() {
            if (!this.canSave) return
            this.saving = true
            this.errors = {}
            try {
                if (this.payloadGroups.length) await this.save(this.payload())
                if (this.idFile && this.missing.includes('id_document')) {
                    await this.uploadIdDocument(this.idFile)
                    this.idFile = null
                }
                if (this.missing.includes('id_document')) {   // passport saved without its photo
                    if (!this.shown.includes('id_document')) this.shown.push('id_document')
                    this.errors = { id_document: this.$t('join_page.error_id_document') }
                    return
                }
                this.$q.notify({
                    classes: 'quasar-notify-positive',
                    message: `✔️ ${this.$t('seller_profile.saved')}`,
                    position: 'bottom',
                    timeout: 1500,
                })
                this.$router.push('/seller/me')
            } catch (e) {
                this.showError(e)
            } finally {
                this.saving = false
            }
        },
    },

    async mounted() {
        await this.fetch()
        this.shown = [...this.missing]
        this.initForm()
    },
}
</script>

<template>
    <div class="profile-form">
        <div v-if="!form" class="form-skeleton">
            <q-skeleton v-for="n in 3" :key="n" type="rect" height="140px" animation="pulse" class="sk-card" />
        </div>

        <template v-else>
            <div v-if="!shown.length" class="all-done">{{ $t('seller_profile.all_done') }}</div>
            <div v-else class="form-hint">{{ $t('seller_profile.form_hint') }}</div>

            <!-- Identity + ID document -->
            <div v-if="has('identity') || has('id_document')" class="card">
                <div class="card-title">{{ $t('seller_profile.group_identity') }}</div>
                <template v-if="has('identity')">
                    <div class="card-hint">{{ $t('join_page.about_hint') }}</div>
                    <q-input v-model="form.first_name" dark outlined dense color="amber" :label="$t('join_page.label_first_name')" :error="!!err('first_name')" :error-message="err('first_name')" maxlength="300" />
                    <q-input v-model="form.last_name" dark outlined dense color="amber" :label="$t('join_page.label_last_name')" :error="!!err('last_name')" :error-message="err('last_name')" maxlength="300" />
                    <q-input v-model="form.date_of_birth" dark outlined dense color="amber" stack-label type="date" :label="$t('join_page.label_date_of_birth')" :error="!!err('date_of_birth')" :error-message="err('date_of_birth')" />
                    <q-select v-model="form.nationality" dark outlined dense color="amber" :options="nationalities" :label="$t('join_page.label_nationality')" :error="!!err('nationality')" :error-message="err('nationality')" />
                    <q-input v-if="form.nationality === 'Other'" v-model="form.nationality_other" dark outlined dense color="amber" :label="$t('join_page.label_nationality_other')" maxlength="300" />
                    <div class="field-label">{{ $t('join_page.label_id_type') }}</div>
                    <q-option-group v-model="form.id_type" :options="idTypes" type="radio" inline dark color="amber" />
                    <q-input v-model="form.id_number" dark outlined dense color="amber" :label="$t('join_page.label_id_number')" :hint="prefill.id_number_masked ? $t('seller_profile.hint_keep_number', { masked: prefill.id_number_masked }) : ''" :error="!!err('id_number')" :error-message="err('id_number')" maxlength="300" />
                    <q-input v-model="form.id_expiry_date" dark outlined dense color="amber" stack-label type="date" :label="$t('seller_profile.label_id_expiry')" :hint="form.id_type === 'passport' ? $t('seller_profile.hint_passport_validity', { months: limits.min_id_validity_months }) : ''" :error="!!err('id_expiry_date')" :error-message="err('id_expiry_date')" />
                    <q-input v-model="form.residential_address" dark outlined dense color="amber" :label="$t('join_page.label_residential_address')" :hint="$t('join_page.hint_residential_address')" :error="!!err('residential_address')" :error-message="err('residential_address')" maxlength="300" />
                    <q-input v-model="form.email" dark outlined dense color="amber" type="email" :label="$t('join_page.label_email')" :hint="$t('join_page.hint_optional')" :error="!!err('email')" :error-message="err('email')" maxlength="300" />
                    <div v-if="form.id_type === 'cccd'" class="card-hint">{{ $t('seller_profile.hint_no_cccd_photo') }}</div>
                </template>
                <template v-if="needsPassportPhoto">
                    <div class="field-label">{{ $t('seller_profile.label_passport_photo') }}</div>
                    <q-file v-model="idFile" dark outlined dense color="amber" accept="image/jpeg,image/png,application/pdf" :label="$t('join_page.documents_add')" :hint="$t('join_page.documents_hint', { mb: limits.max_file_mb })" :error="!!err('id_document')" :error-message="err('id_document')" />
                </template>
            </div>

            <!-- Tax -->
            <div v-if="has('tax')" class="card">
                <div class="card-title">{{ $t('seller_profile.group_tax') }}</div>
                <div class="field-label">{{ $t('join_page.label_tax_resident') }}</div>
                <q-option-group v-model="form.tax_resident" :options="residentOptions" type="radio" inline dark color="amber" />
                <div v-if="err('tax_resident')" class="field-error">{{ err('tax_resident') }}</div>
                <q-input v-model="form.tax_code" dark outlined dense color="amber" :label="$t('join_page.label_tax_code')" :hint="$t('join_page.hint_optional')" maxlength="300" />
            </div>

            <!-- Bank -->
            <div v-if="has('bank')" class="card">
                <div class="card-title">{{ $t('seller_profile.group_bank') }}</div>
                <div class="card-hint">{{ $t('join_page.payout_hint') }}</div>
                <q-select v-model="form.bank_name" dark outlined dense color="amber" :options="banks" :label="$t('join_page.label_bank_name')" :error="!!err('bank_name')" :error-message="err('bank_name')" />
                <q-input v-if="form.bank_name === 'Other'" v-model="form.bank_name_other" dark outlined dense color="amber" :label="$t('join_page.label_bank_name_other')" maxlength="300" />
                <q-input v-model="form.bank_account_number" dark outlined dense color="amber" inputmode="numeric" :label="$t('join_page.label_bank_account_number')" :hint="prefill.bank_account_number_masked ? $t('seller_profile.hint_keep_number', { masked: prefill.bank_account_number_masked }) : ''" :error="!!err('bank_account_number')" :error-message="err('bank_account_number')" maxlength="30" />
                <q-input v-model="form.bank_account_holder" dark outlined dense color="amber" :label="$t('join_page.label_bank_account_holder')" :hint="$t('join_page.hint_bank_account_holder')" :error="!!err('bank_account_holder')" :error-message="err('bank_account_holder')" maxlength="300" />
            </div>

            <!-- Contact + pickup address -->
            <div v-if="has('phone') || has('pickup_address')" class="card">
                <div class="card-title">{{ $t('seller_profile.group_contact') }}</div>
                <q-input v-if="has('phone')" v-model="form.phone" dark outlined dense color="amber" type="tel" :label="$t('join_page.label_phone')" :hint="$t('join_page.hint_phone')" :error="!!err('phone')" :error-message="err('phone')" maxlength="30" />
                <template v-if="has('pickup_address')">
                    <div class="field-label">{{ $t('join_page.label_pickup_address') }}</div>
                    <div class="card-hint">{{ $t('join_page.hint_pickup_address') }}</div>
                    <div v-if="!waitingForAddress" class="saved-note">✔️ {{ $t('seller_profile.address_saved') }}</div>
                    <AddressForm embedded @saved="fetch" />
                </template>
            </div>

            <!-- Agreement -->
            <div v-if="has('agreement')" class="card">
                <div class="card-title">{{ $t('seller_profile.group_agreement') }}</div>
                <a href="/docs/sariko_seller_agreement.html" target="_blank" class="doc-link">{{ $t('join_page.agreement_open') }}</a>
                <q-checkbox v-model="form.agree_accurate" dark color="amber" :label="$t('join_page.agree_accurate')" />
                <q-checkbox v-model="form.agree_data" dark color="amber" :label="$t('join_page.agree_data')" />
                <q-checkbox v-model="form.agree_agreement" dark color="amber" :label="$t('join_page.agree_agreement', { version: data.agreement_version_current })" />
                <div v-if="err('agreed')" class="field-error">{{ err('agreed') }}</div>
                <q-input v-model="form.signature_name" dark outlined dense color="amber" :label="$t('join_page.label_signature')" :hint="fullName ? $t('join_page.hint_signature', { name: fullName }) : ''" :error="!!err('signature_name')" :error-message="err('signature_name')" maxlength="300" />
            </div>

            <template v-if="shown.length">
                <div v-if="err('')" class="form-error">{{ err('') }}</div>
                <div v-if="waitingForAddress" class="card-hint">{{ $t('seller_profile.hint_save_address_first') }}</div>
                <q-btn unelevated no-caps class="btn-save" color="amber" text-color="black" :label="$t('seller_profile.save')" :loading="saving" :disable="!canSave" @click="onSave" />
            </template>
        </template>
    </div>
</template>

<style scoped>
.profile-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-bottom: 96px;   /* clear of the fixed seller nav */
}

.form-hint,
.all-done {
    font-size: 13px;
    color: var(--text-secondary);
}

.card {
    background: rgb(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.card-title::first-letter {
    text-transform: uppercase;
}

.card-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
}

.card-hint {
    font-size: 12px;
    color: var(--text-secondary);
}

.field-label {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 4px;
}

.field-error,
.form-error {
    font-size: 12px;
    color: var(--color-error);
}

.saved-note {
    font-size: 13px;
    color: var(--color-success);
}

.doc-link {
    font-size: 13px;
    color: var(--text-active);
}

.btn-save {
    width: 100%;
    min-height: 44px;
    font-weight: 600;
}

.sk-card {
    border-radius: 12px;
    margin-bottom: 12px;
}
</style>
