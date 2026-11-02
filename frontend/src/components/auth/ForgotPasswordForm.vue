<script>
import { Mail } from 'lucide-vue-next';
import { supabase } from '@/lib/supabase';

export default {
    components: { Mail },

    data() {
        return {
            email: '',
            emailError: null,
            sending: false,
            sent: false,
        }
    },

    methods: {
        validateEmail() {
            if (!this.email) {
                this.emailError = this.$t('forgot_password_page.error_required')
                return false
            }
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
            if (!emailRegex.test(this.email)) {
                this.emailError = this.$t('forgot_password_page.error_invalid')
                return false
            }
            this.emailError = null
            return true
        },

        async onSubmit() {
            if (!this.validateEmail()) return
            this.sending = true
            try {
                const { error } = await supabase.auth.resetPasswordForEmail(this.email, {
                    redirectTo: window.location.origin + '/reset-password'
                })
                if (error) throw error
                this.sent = true
            } catch {
                this.$q.notify({
                    classes: 'quasar-notify-negative',
                    message: this.$t('forgot_password_page.error_failed'),
                    position: 'bottom',
                    timeout: 2000,
                })
            } finally {
                this.sending = false
            }
        }
    }
}
</script>

<template>
    <div class="form">

        <template v-if="!sent">
            <div class="greeting">
                <div class="text-greeting">{{ $t('forgot_password_page.greeting_text') }}</div>
                <div class="subtext-greeting">{{ $t('forgot_password_page.greeting_subtext') }}</div>
            </div>

            <div class="form-field">
                <label class="field-label">
                    <Mail :size="16" /> {{ $t('forgot_password_page.label_email') }}
                </label>
                <q-input
                    v-model="email"
                    dense outlined dark
                    type="email"
                    :placeholder="$t('forgot_password_page.placeholder_email')"
                    :error="!!emailError"
                    :error-message="emailError"
                    @blur="validateEmail"
                    @keyup.enter="onSubmit"
                />
            </div>

            <q-btn
                class="btn-submit"
                no-caps unelevated
                :disable="sending"
                :loading="sending"
                @click="onSubmit"
            >
                {{ sending ? $t('forgot_password_page.button_sending') : $t('forgot_password_page.button_send') }}
            </q-btn>
        </template>

        <template v-else>
            <div class="icon-circle">
                <Mail :size="28" />
            </div>

            <div class="greeting">
                <div class="text-greeting">{{ $t('forgot_password_page.success_title') }}</div>
                <div class="subtext-greeting">{{ $t('forgot_password_page.success_text') }}</div>
            </div>

            <div class="email-box">{{ email }}</div>
        </template>

        <router-link to="/signin" class="link-back">
            {{ $t('forgot_password_page.link_back_to_signin') }}
        </router-link>

    </div>
</template>

<style lang="scss" scoped>
.form {
    display: flex;
    flex-direction: column;
    gap: 20px;
    font-family: $sariko-font-family-secondary;
    
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

.btn-submit {
    padding: 14px;
    background: var(--color-accent, #f5A623);
    color: #121b2f;
    font-weight: 700;
    font-size: 15px;
    border-radius: 12px;
}

.icon-circle {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    align-self: center;
    background: rgba(245, 166, 35, 0.12);
    color: var(--color-accent, #f5A623);
}

.email-box {
    align-self: center;
    max-width: 100%;
    font-weight: 700;
    font-size: 15px;
    color: var(--color-accent, #f5A623);
    background: rgba(245, 166, 35, 0.1);
    border: 1px solid rgba(245, 166, 35, 0.3);
    border-radius: 10px;
    padding: 10px 16px;
    word-break: break-all;
    text-align: center;
}

.link-back {
    text-align: center;
    font-size: 13px;
    color: var(--color-accent, #f5A623);
    text-decoration: none;
    font-weight: 600;
}
</style>
