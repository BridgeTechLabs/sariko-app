<script>
import { Lock, Eye, EyeOff } from 'lucide-vue-next';
import { supabase } from '@/lib/supabase';

export default {
    components: { Lock, Eye, EyeOff },

    data() {
        return {
            newPassword: '',
            confirmPassword: '',
            showNew: false,
            showConfirm: false,
            saving: false,
            newError: null,
            confirmError: null,
        }
    },

    computed: {
        canSave() {
            return this.newPassword.length >= 8 && !this.saving && !this.newError && !this.confirmError
        }
    },

    methods: {
        validateNew() {
            if (!this.newPassword) {
                this.newError = this.$t('reset_password_page.error_required')
                return false
            }
            if (this.newPassword.length < 8) {
                this.newError = this.$t('reset_password_page.error_min_length')
                return false
            }
            this.newError = null
            if (this.confirmPassword) this.validateConfirm()
            return true
        },

        validateConfirm() {
            if (this.confirmPassword && this.confirmPassword !== this.newPassword) {
                this.confirmError = this.$t('reset_password_page.error_mismatch')
                return false
            }
            this.confirmError = null
            return true
        },

        async onSave() {
            if (!this.validateNew()) return
            if (!this.validateConfirm()) return
            if (this.newPassword !== this.confirmPassword) {
                this.confirmError = this.$t('reset_password_page.error_mismatch')
                return
            }

            this.saving = true
            try {
                const { error } = await supabase.auth.updateUser({ password: this.newPassword })
                if (error) throw error

                this.$q.notify({
                    classes: 'quasar-notify-positive',
                    message: `✔️ ${this.$t('reset_password_page.success')}`,
                    position: 'bottom',
                    timeout: 1500,
                })
                await supabase.auth.signOut()
                this.$router.push('/signin')
            } catch (e) {
                this.$q.notify({
                    classes: 'quasar-notify-negative',
                    message: this.$t(e?.code === 'same_password' ? 'common.toast_same_password' : 'common.toast_update_failed'),
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
    <div class="form">

        <div class="greeting">
            <div class="text-greeting">{{ $t('reset_password_page.greeting_text') }}</div>
            <div class="subtext-greeting">{{ $t('reset_password_page.greeting_subtext') }}</div>
        </div>

        <div class="form-field">
            <label class="field-label">
                <Lock :size="16" /> {{ $t('reset_password_page.label_new') }}
            </label>
            <q-input
                v-model="newPassword"
                dense outlined dark
                :type="showNew ? 'text' : 'password'"
                :placeholder="$t('reset_password_page.placeholder_new')"
                :error="!!newError"
                :error-message="newError"
                @blur="validateNew"
            >
                <template #append>
                    <component :is="showNew ? 'EyeOff' : 'Eye'" :size="18" class="eye-icon" @click="showNew = !showNew" />
                </template>
            </q-input>
        </div>

        <div class="form-field">
            <label class="field-label">
                <Lock :size="16" /> {{ $t('reset_password_page.label_confirm') }}
            </label>
            <q-input
                v-model="confirmPassword"
                dense outlined dark
                :type="showConfirm ? 'text' : 'password'"
                :placeholder="$t('reset_password_page.placeholder_confirm')"
                :error="!!confirmError"
                :error-message="confirmError"
                @blur="validateConfirm"
            >
                <template #append>
                    <component :is="showConfirm ? 'EyeOff' : 'Eye'" :size="18" class="eye-icon" @click="showConfirm = !showConfirm" />
                </template>
            </q-input>
        </div>

        <q-btn
            class="btn-save"
            no-caps unelevated
            :disable="!canSave"
            :loading="saving"
            @click="onSave"
        >
            {{ saving ? $t('common.button_label_saving') : $t('reset_password_page.button_save') }}
        </q-btn>

    </div>
</template>

<style scoped>
.form {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.greeting {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    text-align: center;
    margin-bottom: 4px;
}

.text-greeting {
    font-weight: 700;
    font-size: 20px;
}

.subtext-greeting {
    font-size: 12px;
    color: var(--text-secondary);
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

.eye-icon {
    cursor: pointer;
    color: var(--text-secondary);
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
</style>
