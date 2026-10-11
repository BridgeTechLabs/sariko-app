<script>
import { User, Phone, Camera, Store } from 'lucide-vue-next';
import { useAuthStore } from '@/stores/auth/authStore';
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import apiUsers from '@/apis/users/apiUsers';
import { fileToBase64 } from '@/utils/fileToBase64';

export default {
    components: { User, Phone, Camera, Store },

    data() {
        return {
            name: '',
            phone: '',
            avatarUrl: '',
            avatarPreview: null,
            uploadingAvatar: false,
            saving: false,
            nameError: null,
            phoneError: null,
            storeName: '',
            storeNameError: null,
        }
    },

    computed: {
        authStore() {
            return useAuthStore()
        },
        user() {
            return this.authStore.user
        },
        isSeller() {
            return !!this.user?.isSeller
        },
        sellerInfo() {
            return useDashboardStore().sellerInfo
        },
        initials() {
            if (!this.name) return '?'
            return this.name.trim().charAt(0).toUpperCase()
        },
        isDirty() {
            return (
                this.name !== (this.user?.fullName || '') ||
                this.phone !== (this.user?.phone || '') ||
                this.avatarUrl !== (this.user?.avatarUrl || '') ||
                (this.isSeller && this.storeName !== (this.sellerInfo?.store_name || ''))
            )
        },
        canSave() {
            return this.isDirty && !this.saving && !this.nameError && !this.phoneError && !this.storeNameError && !this.uploadingAvatar
        }
    },

    async mounted() {
        this.name = this.user?.fullName || ''
        this.phone = this.user?.phone || ''
        this.avatarUrl = this.user?.avatarUrl || ''
        if (this.isSeller) {
            if (!this.sellerInfo) await useDashboardStore().fetchSellerInfo()
            this.storeName = this.sellerInfo?.store_name || ''
        }
    },

    methods: {
        triggerFileInput() {
            this.$refs.fileInput.click()
        },

        async onFileSelected(event) {
            const file = event.target.files[0]
            if (!file) return

            if (!file.type.startsWith('image/')) {
                this.$q.notify({ classes: 'quasar-notify-negative', message: this.$t('edit_profile_page.error_avatar_type'), position: 'bottom', timeout: 2000 })
                return
            }
            if (file.size > 2 * 1024 * 1024) {
                this.$q.notify({ classes: 'quasar-notify-negative', message: this.$t('edit_profile_page.error_avatar_size'), position: 'bottom', timeout: 2000 })
                return
            }

            this.avatarPreview = URL.createObjectURL(file)
            this.uploadingAvatar = true

            try {
                const imageBase64 = await fileToBase64(file)
                const res = await apiUsers.uploadAvatar(imageBase64, file.type)
                this.avatarUrl = res.avatar_url
            } catch (e) {
                console.error('ProfileForm - avatar upload -', e)
                this.avatarPreview = null
                this.$q.notify({ classes: 'quasar-notify-negative', message: this.$t('edit_profile_page.error_avatar_upload'), position: 'bottom', timeout: 2000 })
            } finally {
                this.uploadingAvatar = false
            }
        },

        validateName() {
            if (!this.name || !this.name.trim()) {
                this.nameError = this.$t('edit_profile_page.validation_name_required')
                return false
            }
            this.nameError = null
            return true
        },

        // Mirrors backend RequestUpdateProfile.store_name: required, ≤ 50 chars after trim
        validateStoreName() {
            const value = this.storeName.trim()
            this.storeNameError = !value ? this.$t('edit_profile_page.validation_store_name_required')
                : value.length > 50 ? this.$t('edit_profile_page.validation_store_name_too_long')
                : null
            return !this.storeNameError
        },

        validatePhone() {
            if (!this.phone) {
                this.phoneError = null
                return true
            }
            // Accept VN phone formats: 0xxxxxxxxx or +84xxxxxxxxx
            const normalized = this.phone.replace(/\s|-/g, '')
            const valid = /^(0|\+84)\d{9,10}$/.test(normalized)
            if (!valid) {
                this.phoneError = this.$t('edit_profile_page.validation_phone_invalid')
                return false
            }
            this.phoneError = null
            return true
        },

        async onSave() {
            if (!this.validateName()) return
            if (!this.validatePhone()) return
            if (this.isSeller && !this.validateStoreName()) return

            this.saving = true
            try {
                await apiUsers.updateProfile({
                    name: this.name.trim(),
                    phone: this.phone ? this.phone.trim() : null,
                    avatar_url: this.avatarUrl ? this.avatarUrl.trim() : null,
                    store_name: this.isSeller ? this.storeName.trim() : undefined,
                })
                if (this.isSeller && this.sellerInfo) this.sellerInfo.store_name = this.storeName.trim()

                // Update local store state
                if (this.user) {
                    this.user.fullName = this.name.trim()
                    this.user.phone = this.phone ? this.phone.trim() : null
                    this.user.avatarUrl = this.avatarUrl ? this.avatarUrl.trim() : null
                }

                this.$q.notify({
                    classes: 'quasar-notify-positive',
                    message: `✔️ ${this.$t('common.toast_update_success')}`,
                    position: 'bottom',
                    timeout: 1500,
                })
                this.$router.push('/account')
            } catch (e) {
                console.error('ProfileForm - onSave - ', e)
                this.$q.notify({
                    classes: 'quasar-notify-negative',
                    message: this.$t('common.toast_update_failed'),
                    position: 'bottom',
                    timeout: 2000,
                })
            } finally {
                this.saving = false
            }
        }
    }
}
</script>

<template>
    <div class="profile-form">
        <!-- Name field -->
        <div class="form-field">
            <label class="field-label">
                <User :size="16" /> {{ $t('edit_profile_page.label_name') }}
            </label>
            <q-input
                v-model="name"
                dense
                outlined
                dark
                :placeholder="$t('edit_profile_page.placeholder_name')"
                :error="!!nameError"
                :error-message="nameError"
                @blur="validateName"
            />
        </div>

        <!-- Store name (sellers only; the shop link/slug stays the same) -->
        <div v-if="isSeller" class="form-field">
            <label class="field-label">
                <Store :size="16" /> {{ $t('edit_profile_page.label_store_name') }}
            </label>
            <q-input
                v-model="storeName"
                dense
                outlined
                dark
                maxlength="50"
                :placeholder="$t('edit_profile_page.placeholder_store_name')"
                :hint="$t('edit_profile_page.helper_store_name')"
                :error="!!storeNameError"
                :error-message="storeNameError"
                @blur="validateStoreName"
            />
        </div>

        <!-- Phone field -->
        <div class="form-field">
            <label class="field-label">
                <Phone :size="16" /> {{ $t('edit_profile_page.label_phone') }}
            </label>
            <q-input
                v-model="phone"
                dense
                outlined
                dark
                type="tel"
                :placeholder="$t('edit_profile_page.placeholder_phone')"
                :error="!!phoneError"
                :error-message="phoneError"
                @blur="validatePhone"
            />
        </div>

        <!-- Avatar upload -->
        <div class="form-field">
            <label class="field-label">
                <Camera :size="16" /> {{ $t('edit_profile_page.label_avatar') }}
            </label>
            <div class="avatar-upload-wrap" @click="triggerFileInput">
                <div class="avatar-upload-circle">
                    <img v-if="avatarPreview || avatarUrl" :src="avatarPreview || avatarUrl" class="avatar-preview-img" />
                    <span v-else class="avatar-initials-text">{{ initials }}</span>
                </div>
                <div class="avatar-upload-badge">
                    <q-spinner v-if="uploadingAvatar" size="12px" color="black" />
                    <Camera v-else :size="12" />
                </div>
            </div>
            <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFileSelected" />
            <span class="avatar-hint">{{ $t('edit_profile_page.helper_avatar') }}</span>
        </div>

        <!-- Save button -->
        <q-btn
            class="btn-save"
            no-caps
            unelevated
            :disable="!canSave"
            :loading="saving"
            @click="onSave"
        >
            {{ saving ? $t('common.button_label_saving') : $t('common.button_label_save') }}
        </q-btn>
    </div>
</template>

<style scoped>
.profile-form {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.form-field {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.field-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

.avatar-upload-wrap {
    position: relative;
    width: 80px;
    cursor: pointer;
    align-self: center;
}

.avatar-upload-circle {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    overflow: hidden;
    background: rgba(245, 166, 35, 0.15);
    border: 1px solid rgba(245, 166, 35, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
}

.avatar-preview-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.avatar-initials-text {
    font-size: 28px;
    font-weight: 700;
    color: var(--color-accent);
}

.avatar-upload-badge {
    position: absolute;
    bottom: 0;
    right: 0;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: var(--color-accent);
    color: #000;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid var(--bg-main);
}

.avatar-hint {
    font-size: 12px;
    color: var(--text-secondary);
    text-align: center;
}

.btn-save {
    margin-top: 12px;
    padding: 14px;
    background: var(--color-accent, #f5A623);
    color: #121b2f;
    font-weight: 700;
    font-size: 15px;
    border-radius: 12px;
}

.btn-save:disabled {
    background: rgba(245, 166, 35, 0.3);
    color: rgba(18, 27, 47, 0.5);
}
</style>
