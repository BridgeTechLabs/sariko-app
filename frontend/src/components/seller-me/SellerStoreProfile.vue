<script>
import { ChevronRight } from 'lucide-vue-next';
import { mapState, mapActions } from 'pinia';
import SectionTitle from '@/components/shared/SectionTitle.vue';
import { useAuthStore } from '@/stores/auth/authStore';
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import { useProfileCompletionStore } from '@/stores/seller/profileCompletionStore';

// Fields edited here, one sheet each, all saved through PATCH /users/me/profile (spec T170 QĐ B).
// ID, tax, bank and the agreement are read-only rows: a missing one opens the existing form.
const SHEETS = {
    store_name:  { label: 'edit_profile_page.label_store_name', hint: 'edit_profile_page.helper_store_name', max: 50 },
    description: { label: 'seller_profile.row_description', hint: 'seller_profile.hint_description', max: 1000 },
    phone:       { label: 'edit_profile_page.label_phone', hint: '', max: 30 },
    name:        { label: 'seller_profile.row_contact_name', hint: 'seller_profile.hint_contact_name', max: 300 },
}

export default {
    name: 'SellerStoreProfile',

    components: { ChevronRight, SectionTitle },

    data() {
        return {
            editing: null,      // SHEETS key of the open sheet
            value: '',
            fieldError: '',
            formError: '',
            saving: false,
            uploading: false,
            loading: true,
        }
    },

    computed: {
        ...mapState(useAuthStore, ['user']),
        ...mapState(useDashboardStore, ['sellerInfo']),
        ...mapState(useProfileCompletionStore, { completion: 'data', missing: 'missing' }),

        sheet() {
            return SHEETS[this.editing] || {}
        },

        initials() {   // same letter as the Me header avatar
            return (this.user?.fullName || '?').trim().charAt(0).toUpperCase()
        },

        // One row per missing_groups entry (= the Edit Profile badge count when missing).
        legalSections() {
            const p = this.completion?.prefill || {}
            const row = (group, label, value) => ({ group, label: this.$t(label), value, missing: this.missing.includes(group) })
            const owner = [row('identity', 'seller_profile.group_identity', p.full_name)]
            if (this.missing.includes('id_document')) owner.push(row('id_document', 'seller_profile.label_passport_photo', ''))
            const resident = p.tax_resident == null ? '' : this.$t(`join_page.resident_${p.tax_resident ? 'yes' : 'no'}`)
            return [
                { title: 'seller_profile.section_owner', rows: owner },
                { title: 'seller_profile.section_tax_bank', rows: [
                    row('tax', 'seller_profile.group_tax', p.tax_code || resident),
                    row('bank', 'seller_profile.group_bank', [p.bank_name, p.bank_account_number_masked].filter(Boolean).join(' ')),
                ] },
                { title: 'seller_profile.section_signature', rows: [
                    row('agreement', 'seller_profile.group_agreement', this.$t('seller_profile.signed')),
                ] },
            ]
        },
    },

    // Also on coming back from the pickup address or the legal form: the rows follow.
    mounted() {
        this.reload()
    },

    methods: {
        ...mapActions(useDashboardStore, ['fetchSellerInfo', 'saveStoreProfile']),
        ...mapActions(useAuthStore, ['uploadAvatar']),
        ...mapActions(useProfileCompletionStore, { fetchCompletion: 'fetch' }),

        async reload() {
            this.loading = true
            await Promise.all([this.fetchSellerInfo(), this.fetchCompletion()])
            this.loading = false
        },

        // Description: the sheet needs the saved text first, or Save would overwrite it with "" (QĐ I, Q).
        open(key) {
            if (this.sellerInfo?.description === undefined) return   // also an older backend without the field
            this.editing = key
            this.value = (key === 'name' ? this.user?.fullName : this.sellerInfo[key]) || ''
            this.fieldError = ''
            this.formError = ''
        },

        close() {
            if (!this.saving) this.editing = null
        },

        validate() {
            const v = this.value.trim()
            if (this.editing === 'store_name' && !v) this.fieldError = this.$t('edit_profile_page.validation_store_name_required')
            else if (this.editing === 'name' && !v) this.fieldError = this.$t('edit_profile_page.validation_name_required')
            // Same check as the buyer form; the backend turns the number into +84...
            else if (this.editing === 'phone' && !/^(0|\+84)\d{9,10}$/.test(v.replace(/\s|-/g, ''))) this.fieldError = this.$t('edit_profile_page.validation_phone_invalid')
            else this.fieldError = ''
            return !this.fieldError
        },

        async save() {
            if (!this.validate()) return
            this.saving = true
            this.formError = ''
            try {
                await this.saveStoreProfile({ [this.editing]: this.value.trim() })
                this.editing = null
                this.notifySaved()
            } catch (e) {
                console.error('SellerStoreProfile - save -', e)
                if (e?.response?.status === 422 && this.editing === 'phone') this.fieldError = this.$t('edit_profile_page.validation_phone_invalid')
                else this.formError = this.$t('seller_profile.error_save')
            } finally {
                this.saving = false
            }
        },

        pickPhoto() {
            if (!this.uploading) this.$refs.photo.click()
        },

        async onPhoto(event) {
            const file = event.target.files[0]
            event.target.value = ''
            if (!file) return
            const error = !file.type.startsWith('image/') ? 'edit_profile_page.error_avatar_type'
                : file.size > 2 * 1024 * 1024 ? 'edit_profile_page.error_avatar_size' : null
            if (error) {
                this.$q.notify({ classes: 'quasar-notify-negative', message: this.$t(error), position: 'bottom', timeout: 2000 })
                return
            }
            this.uploading = true
            try {
                await this.saveStoreProfile({ avatar_url: await this.uploadAvatar(file) })
                this.notifySaved()
            } catch (e) {
                console.error('SellerStoreProfile - photo -', e)
                this.$q.notify({ classes: 'quasar-notify-negative', message: this.$t('edit_profile_page.error_avatar_upload'), position: 'bottom', timeout: 2000 })
            } finally {
                this.uploading = false
            }
        },

        notifySaved() {
            this.$q.notify({ classes: 'quasar-notify-positive', message: `✔️ ${this.$t('common.toast_update_success')}`, position: 'bottom', timeout: 1500 })
        },
    },
}
</script>

<template>
    <div class="store-profile">
        <div v-if="loading && !(sellerInfo && completion)" class="card card--pad">
            <q-skeleton v-for="n in 4" :key="n" type="text" animation="pulse" />
        </div>

        <template v-else>
            <div v-if="!loading && !(sellerInfo && completion)" class="load-error">
                {{ $t('seller_profile.load_error') }}
                <q-btn flat no-caps dense class="link-btn" :label="$t('seller_me.earnings_retry')" @click="reload" />
            </div>

            <!-- STORE: edited here, one sheet per row -->
            <SectionTitle>{{ $t('seller_profile.section_store') }}</SectionTitle>
            <div class="card">
                <div class="row row--tap" @click="pickPhoto">
                    <q-avatar size="40px" class="thumb">
                        <img v-if="user?.avatarUrl" :src="user.avatarUrl" alt="">
                        <span v-else>{{ initials }}</span>
                    </q-avatar>
                    <span class="main label">{{ $t('seller_profile.row_photo') }}</span>
                    <q-spinner v-if="uploading" size="16px" color="amber" />
                    <ChevronRight v-else :size="16" class="chev" />
                    <input ref="photo" type="file" accept="image/*" hidden @change="onPhoto">
                </div>

                <div class="row row--tap" @click="open('store_name')">
                    <span class="main label">{{ $t('edit_profile_page.label_store_name') }}</span>
                    <span class="value">{{ sellerInfo?.store_name }}</span>
                    <ChevronRight :size="16" class="chev" />
                </div>

                <div class="row row--tap" @click="open('description')">
                    <div class="main">
                        <div class="label">{{ $t('seller_profile.row_description') }}</div>
                        <div class="desc" :class="{ 'desc--empty': !sellerInfo?.description }">
                            {{ sellerInfo?.description || $t('seller_profile.description_empty') }}
                        </div>
                    </div>
                    <ChevronRight :size="16" class="chev" />
                </div>

                <div class="row row--tap" @click="open('phone')">
                    <span class="main label">{{ $t('edit_profile_page.label_phone') }}</span>
                    <span v-if="missing.includes('phone')" class="missing"><i />{{ $t('seller_profile.missing') }}</span>
                    <span v-else class="value">{{ sellerInfo?.phone }}</span>
                    <ChevronRight :size="16" class="chev" />
                </div>

                <div class="row row--tap" @click="open('name')">
                    <div class="main">
                        <div class="label">{{ $t('seller_profile.row_contact_name') }}</div>
                        <div class="sub">{{ $t('seller_profile.hint_contact_name') }}</div>
                    </div>
                    <span class="value">{{ user?.fullName }}</span>
                    <ChevronRight :size="16" class="chev" />
                </div>

                <router-link to="/account/address" class="row row--tap">
                    <span class="main label">{{ $t('join_page.label_pickup_address') }}</span>
                    <span v-if="missing.includes('pickup_address')" class="missing"><i />{{ $t('seller_profile.missing') }}</span>
                    <span v-else class="value">{{ sellerInfo?.address }}</span>
                    <ChevronRight :size="16" class="chev" />
                </router-link>
            </div>

            <!-- OWNER / TAX & BANK / SIGNATURE: read only; a missing row opens the existing form -->
            <template v-if="completion">
                <template v-for="s in legalSections" :key="s.title">
                    <SectionTitle class="gap">{{ $t(s.title) }}</SectionTitle>
                    <div class="card">
                        <template v-for="r in s.rows" :key="r.group">
                            <router-link v-if="r.missing" to="/seller/me/profile/legal" class="row row--tap">
                                <span class="main label">{{ r.label }}</span>
                                <span class="missing"><i />{{ $t('seller_profile.missing') }}</span>
                                <ChevronRight :size="16" class="chev" />
                            </router-link>
                            <div v-else class="row">
                                <span class="main label">{{ r.label }}</span>
                                <span class="value">{{ r.value }}</span>
                            </div>
                        </template>
                    </div>
                </template>
            </template>
        </template>

        <q-dialog :model-value="!!editing" position="bottom" @update:model-value="v => !v && close()">
            <div class="sheet">
                <!-- Swipe only here: inside the description box a swipe scrolls the text -->
                <div v-touch-swipe.down="close" class="sheet-grip">
                    <div class="sheet-handle" />
                    <div class="sheet-title">{{ $t(sheet.label) }}</div>
                </div>
                <!-- Not a q-input hint: Quasar positions hints absolutely, a 2-line one runs into Save -->
                <div v-if="sheet.hint" class="sheet-hint">{{ $t(sheet.hint) }}</div>
                <q-input v-model="value" dark outlined color="amber" autofocus
                    :type="editing === 'description' ? 'textarea' : editing === 'phone' ? 'tel' : 'text'"
                    :autogrow="editing === 'description'" :counter="editing === 'description'" :maxlength="sheet.max"
                    :error="!!fieldError" :error-message="fieldError"
                    @update:model-value="fieldError = ''" />
                <div v-if="formError" class="form-error">{{ formError }}</div>
                <q-btn unelevated no-caps class="btn-save" color="amber" text-color="black"
                    :label="$t('common.button_label_save')" :loading="saving" @click="save" />
            </div>
        </q-dialog>
    </div>
</template>

<style scoped>
/* "Grouped list" like Settings: one surface per section, hairline dividers, 8px rhythm */
.store-profile {
    padding-bottom: 96px;   /* clear of the fixed seller nav */
}

.card {
    background: rgb(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
}

.card--pad {
    padding: 16px;
}

.gap {
    margin-top: 24px;
}

.row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 16px;
    min-height: 52px;
    color: var(--text-primary);
    text-decoration: none;
}

.row + .row {
    border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.row--tap {
    cursor: pointer;
}

.main {
    flex: 1;
    min-width: 0;
}

.label {
    font-size: 14px;
    font-weight: 500;
}

.sub {
    margin-top: 2px;
    font-size: 12px;
    color: var(--text-secondary);
}

.value {
    max-width: 55%;
    font-size: 14px;
    color: var(--text-secondary);
    text-align: right;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.desc {
    margin-top: 2px;
    font-size: 13px;
    line-height: 1.45;
    color: var(--text-secondary);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.desc--empty {
    color: var(--text-muted);
}

.missing {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--color-error);
}

.missing i {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--color-error);
}

.thumb {
    flex-shrink: 0;
    background: rgba(245, 166, 35, 0.15);
    color: var(--color-accent);
    font-weight: 700;
}

.thumb img {
    object-fit: cover;
}

.chev {
    flex-shrink: 0;
    color: var(--text-muted);
}

.load-error {
    margin-bottom: 16px;
    font-size: 13px;
    color: var(--color-error);
}

.link-btn {
    color: var(--color-accent);
    font-weight: 600;
}

.sheet {
    width: 100%;
    max-width: 600px;
    padding: 8px 16px calc(16px + env(safe-area-inset-bottom, 0));
    background: var(--bg-surface);
    border-radius: 16px 16px 0 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.sheet-grip {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.sheet-handle {
    align-self: center;
    width: 36px;
    height: 4px;
    border-radius: 2px;
    background: rgba(255, 255, 255, 0.2);
}

.sheet-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
}

.sheet-hint {
    margin-top: -4px;
    font-size: 12px;
    color: var(--text-secondary);
}

.form-error {
    font-size: 12px;
    color: var(--color-error);
}

.btn-save {
    min-height: 44px;
    font-weight: 700;
}
</style>
