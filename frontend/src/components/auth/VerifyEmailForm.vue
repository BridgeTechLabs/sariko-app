<script>
import { Mail } from 'lucide-vue-next';
import { mapState, mapActions } from 'pinia';
import { useAuthStore } from '@/stores/auth/authStore';

export default {
    components: { Mail },

    computed: {
        ...mapState(useAuthStore, ["isResendingVerification"]),

        email() {
            return this.$route.query.email || ''
        }
    },

    methods: {
        ...mapActions(useAuthStore, ["onClickedResendVerification"]),

        onResend() {
            this.onClickedResendVerification(this.email)
        }
    }
}
</script>

<template>
    <div class="form">

        <div class="icon-circle">
            <Mail :size="28" />
        </div>

        <div class="greeting">
            <div class="text-greeting">{{ $t('verify_email_page.title') }}</div>
            <div class="subtext-greeting">{{ $t('verify_email_page.text_sent') }}</div>
        </div>

        <div class="email-box">{{ email }}</div>

        <div class="greeting">
            <div class="subtext-greeting">{{ $t('verify_email_page.instruction') }}</div>
            <div class="hint-text">{{ $t('verify_email_page.hint') }}</div>
        </div>

        <q-btn
            class="btn-submit"
            no-caps unelevated
            :disable="isResendingVerification"
            :loading="isResendingVerification"
            @click="onResend"
        >
            {{ $t('verify_email_page.button_resend') }}
        </q-btn>

        <router-link to="/signin" class="link-back">
            {{ $t('verify_email_page.link_back_to_signin') }}
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

.hint-text {
    font-size: 12px;
    color: var(--text-secondary);
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

.btn-submit {
    padding: 14px;
    background: var(--color-accent, #f5A623);
    color: #121b2f;
    font-weight: 700;
    font-size: 15px;
    border-radius: 12px;
}

.link-back {
    text-align: center;
    font-size: 13px;
    color: var(--color-accent, #f5A623);
    text-decoration: none;
    font-weight: 600;
}
</style>
