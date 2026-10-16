<script>
import { Smartphone, UserRoundPlus } from 'lucide-vue-next';
import { mapState, mapActions } from 'pinia';
import { useAuthStore } from '@/stores/auth/authStore';

export default {
    components: {
        UserRoundPlus
    },

    computed: {
        ...mapState(useAuthStore, [
            "errors",
            "inputSignUpFullName",
            "inputSignUpEmail",
            "inputSignUpPassword",
            "inputSignUpAgreed",
            "isLoading"
        ])
    },

    methods: {
        ...mapActions(useAuthStore, [
            "onClickedSignup"
        ])
    }
}
</script>

<template>
    <q-btn flat no-caps
    type="submit"
    :loading="isLoading"
    :disable="Object.values(errors).some((e) => !!e) || !inputSignUpFullName || !inputSignUpEmail || !inputSignUpPassword || !inputSignUpAgreed"
    class="button-signup">
        <UserRoundPlus class="icon" /> {{ $t('auth_page.auth_input_fields.signup.button_label_text_signup') }}
    </q-btn>
</template>

<style lang="scss" scoped>

.icon {
    margin-right: 10px;
}


.button-signup {
    width: 100%;
    background-color: $accent;
    color: var(--bg-main);
    font-weight: 700;
    border-radius: 1.5rem;
    padding: 10px 0px;
}

.spinner {
    display: flex;
    justify-content: center;
    background-color: $accent;
    color: var(--bg-main);
    font-weight: 700;
    border-radius: 1.5rem;
    padding: 10px 0px;
    font-size: 20px;
}
</style>