<script>
import { mapState, mapActions } from 'pinia';
import { useAccountV2Store } from '@/stores/v2/account/accountStore';
import BaseTextField from '@/components/v2/shared/BaseTextField.vue';
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';

export default {
    components: { BaseTextField, BaseIcon },

    data() {
        return {
            showNew: false,
            showConfirm: false,
        }
    },

    computed: {
        ...mapState(useAccountV2Store, [
            'passwordForm', 'passwordFormSubmitted', 'passwordNewTouched', 'passwordConfirmTouched',
            'isPasswordLengthValid', 'isPasswordConfirmValid',
        ]),

        newError() {
            return (this.passwordFormSubmitted || this.passwordNewTouched) && !this.isPasswordLengthValid
                ? this.$t('account_v2.password_new_error')
                : null
        },

        confirmError() {
            return (this.passwordFormSubmitted || this.passwordConfirmTouched) && !this.isPasswordConfirmValid
                ? this.$t('account_v2.password_confirm_error')
                : null
        },
    },

    methods: {
        ...mapActions(useAccountV2Store, ['initPasswordForm']),

        // Leaving a field empty doesn't count — no error before the user has typed anything
        onBlurNew() {
            if (this.passwordForm.newPassword) useAccountV2Store().passwordNewTouched = true
        },

        onBlurConfirm() {
            if (this.passwordForm.confirmPassword) useAccountV2Store().passwordConfirmTouched = true
        },
    },

    created() {
        this.initPasswordForm()
    },
}
</script>

<template>
    <div class="change-password-form">
        <BaseTextField
            v-model="passwordForm.newPassword"
            size="lg"
            icon="lock"
            required
            autocomplete="new-password"
            :type="showNew ? 'text' : 'password'"
            :label="$t('account_v2.password_new')"
            :placeholder="$t('account_v2.password_new_placeholder')"
            :hint="$t('account_v2.password_new_hint')"
            :error="newError"
            @blur="onBlurNew"
        >
            <template #trailing>
                <button
                    class="toggle-btn"
                    type="button"
                    :aria-label="showNew ? $t('account_v2.password_hide') : $t('account_v2.password_show')"
                    @click="showNew = !showNew"
                >
                    <BaseIcon :name="showNew ? 'eye-off' : 'eye'" :size="20" />
                </button>
            </template>
        </BaseTextField>

        <BaseTextField
            v-model="passwordForm.confirmPassword"
            size="lg"
            icon="lock"
            required
            autocomplete="new-password"
            :type="showConfirm ? 'text' : 'password'"
            :label="$t('account_v2.password_confirm')"
            :placeholder="$t('account_v2.password_confirm_placeholder')"
            :error="confirmError"
            @blur="onBlurConfirm"
        >
            <template #trailing>
                <button
                    class="toggle-btn"
                    type="button"
                    :aria-label="showConfirm ? $t('account_v2.password_hide') : $t('account_v2.password_show')"
                    @click="showConfirm = !showConfirm"
                >
                    <BaseIcon :name="showConfirm ? 'eye-off' : 'eye'" :size="20" />
                </button>
            </template>
        </BaseTextField>
    </div>
</template>

<style scoped>
.change-password-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-24);
}

.toggle-btn {
    flex-shrink: 0;
    display: flex;
    padding: 0;
    border: none;
    background: transparent;
    color: var(--icon-muted);
    cursor: pointer;
}
</style>
