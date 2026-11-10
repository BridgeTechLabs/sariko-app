<script>
import { User, Phone, Camera } from 'lucide-vue-next';
import { useAuthStore } from '@/stores/auth/authStore';

export default {
    components: { User, Phone, Camera },

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
        }
    },

    computed: {
        authStore() {
            return useAuthStore()
        },
        user() {
            return this.authStore.user
        },
        initials() {
            if (!this.name) return '?'
            return this.name.trim().charAt(0).toUpperCase()
        },
        isDirty() {
            return (
                this.name !== (this.user?.fullName || '') ||
                this.phone !== (this.user?.phone || '') ||
                this.avatarUrl !== (this.user?.avatarUrl || '')
            )
        },
        canSave() {
            return this.isDirty && !this.saving && !this.nameError && !this.phoneError && !this.uploadingAvatar
        }
    },

    // Buyers only: the router sends sellers to their Store profile (/seller/me/profile).
    mounted() {
        this.name = this.user?.fullName || ''
        this.phone = this.user?.phone || ''
        this.avatarUrl = this.user?.avatarUrl || ''
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
                this.avatarUrl = await this.authStore.uploadAvatar(file)
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

            this.saving = true
            try {
                await this.authStore.updateProfile({
                    name: this.name.trim(),
                    phone: this.phone ? this.phone.trim() : null,
                    avatar_url: this.avatarUrl ? this.avatarUrl.trim() : null,
                })

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
