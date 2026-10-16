<script>
import { mapState, mapWritableState, mapActions } from 'pinia';
import { useAuthStore } from '@/stores/auth/authStore';
import { UserRound, Mail, LockKeyhole } from 'lucide-vue-next';
import ButtonSignup from '@/components/auth/form-signup/ButtonSignup.vue';
export default {

    components: {
        UserRound,
        Mail,
        LockKeyhole,
        ButtonSignup
    },

    data() {
        return {

        }
    },

    computed: {
        ...mapWritableState(useAuthStore, [
            "inputSignUpFullName",
            "inputSignUpEmail",
            "inputSignUpPassword",
            "isSelectedSignUpRoleSeller",
            "errors",
            "isLoading"
        ])
    },

    methods: {
        ...mapActions(useAuthStore, [
            "validateField",
            "onClickedSignup"
        ])
    }
}
</script>

<template>

    <q-form class="container" @submit.prevent="onClickedSignup">

        <div class="greeting">
            <div class="text-greeting">
                {{ $t('auth_page.auth_input_fields.signup.greeting_text_signup') }} 👋
            </div>
            <div class="subtext-greeting">
                {{ $t('auth_page.auth_input_fields.signup.greeting_subtext_signup') }}
            </div>
        </div>

        <div class="input-label">
            {{ $t('auth_page.auth_input_fields.common.input_label_full_name') }}
        </div>

        <div class="input-container">
            <q-input
            dense
            outlined
            type="text"
            class="input"
            bg-color="bgInputField"
            :placeholder="$t('auth_page.auth_input_fields.common.placeholder_full_name')"
            :error="!!errors.inputSignUpFullName"
            :error-message="errors.inputSignUpFullName"
            @blur="validateField('inputSignUpFullName')"
            v-model="inputSignUpFullName"
            >
                <template v-slot:prepend>
                     <UserRound color="white" class="icon"/>
                </template>
                <template v-slot:hint>
                    <span class="hint-text">{{ $t('auth_page.auth_input_fields.common.hint_full_name') }}</span>
                </template>
            </q-input>
        </div>

        <div class="input-label">
            {{ $t('auth_page.auth_input_fields.common.input_label_email') }}
        </div>

        <div class="input-container">
            <q-input
            dense
            outlined
            type="text"
            class="input"
            bg-color="bgInputField"
            :placeholder="$t('auth_page.auth_input_fields.common.placeholder_email')"
            :error="!!errors.inputSignUpEmail"
            :error-message="errors.inputSignUpEmail"
            @blur="validateField('inputSignUpEmail')"
            v-model="inputSignUpEmail"
            >
                <template v-slot:prepend>
                     <Mail color="white" class="icon"/>
                </template>

                <template v-slot:hint>
                    <span class="hint-text">{{ $t('auth_page.auth_input_fields.common.hint_email') }}</span>
                </template>
            </q-input>
        </div>

        <div class="input-label">
            {{ $t('auth_page.auth_input_fields.common.input_label_password') }}
        </div>

        <div class="input-container">
            <q-input
            dense
            outlined
            type="password"
            class="input"
            bg-color="bgInputField"
            :placeholder="$t('auth_page.auth_input_fields.common.placeholder_password')"
            :error="!!errors.inputSignUpPassword"
            :error-message="errors.inputSignUpPassword"
            @blur="validateField('inputSignUpPassword')"
            
            v-model="inputSignUpPassword"
            >
                <template v-slot:prepend>
                     <LockKeyhole color="white" class="icon"/>
                </template>

                <template v-slot:hint>
                    <span class="hint-text">{{ $t('auth_page.auth_input_fields.common.hint_password') }}</span>
                </template>
                
            </q-input>
        </div>

        <!-- <div class="input-label">
            {{ $t('auth_page.auth_input_fields.common.input_label_role_selection') }}
        </div> -->

        <!-- <div class="input-role-selection">
            <div @click="isSelectedSignUpRoleSeller=false" 
            :class="{'container-role': true, 'container-role-active': !isSelectedSignUpRoleSeller}">
                <div class="icon-role">
                    🛍️
                </div>
                <div class="role">
                    <span class="text-role">
                        {{ $t('auth_page.auth_input_fields.signup.title_text_role_buyer') }}
                    </span>
                    <br>
                    <span class="subtext-role">
                        {{ $t('auth_page.auth_input_fields.signup.title_subtext_role_buyer') }}
                    </span>
                </div>
            </div>
            <div @click="isSelectedSignUpRoleSeller=true" 
            :class="{'container-role': true, 'container-role-active': isSelectedSignUpRoleSeller}">
                <div class="icon-role">
                    🏪
                </div>
                <div class="role">
                    <span class="text-role">
                        {{ $t('auth_page.auth_input_fields.signup.title_text_role_seller') }}
                    </span>
                    <br>
                    <span class="subtext-role">
                        {{ $t('auth_page.auth_input_fields.signup.title_subtext_role_seller') }}
                    </span>
                </div>
            </div>
        </div> -->

        <div class="button-signup">
            <ButtonSignup />
        </div>

        <router-link to="/home" class="link-home">
            {{ $t('auth_page.link_back_to_home') }}
        </router-link>
    </q-form>

</template>

<style lang="scss" scoped>

.container {
    font-family: $sariko-font-family-secondary;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
    width: 80%;
    margin: auto;
}

.greeting {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    margin-bottom: 20px;
}

.text-greeting {
    font-family: $sariko-font-family-primary;
    font-weight: 700;
    font-size: 22px;
}

.subtext-greeting {
    font-family: $sariko-font-family-secondary;
    font-weight: 700;
    font-size: 10px;
    color: rgb(122, 140, 174);
}

.input-label {
    font-weight: 700;
    font-size: 10px;
    margin-bottom: 5px;
}

.input-container {
    display: flex;
    align-items: center;
    width: 100%;
    border-radius: .75rem;
    margin-bottom: 10px;
}

.icon {
    margin-right: 10px;
}

.input {
    width: 100%;
}

.input-role-selection {
    display: flex;
    justify-content: space-between;
    width: 100%;
}

.container-role {
    display: flex;
    justify-content: center;
    align-items: center;
    background-color: red;
    justify-self: flex-end;
    width: 49%;
}

.container-role {
    display: flex;
    justify-content: center;
    align-items: center;
    justify-self: flex-start;
    width: 49%;
    padding: 12px 0px 15px 0px;
    border-radius: 1rem;
    background-color: var(--bg-surface);
}

.container-role-active {
    border: 1px solid $accent;
    background-color: #2c261f;
}

.icon-role {
    margin-right: 7px;
}

.role {
    line-height: 0.8;
}

.text-role {
    font-weight: 700;
    font-size: 12px
}

.subtext-role {
    font-weight: 700;
    font-size: 9px;
    color: rgb(122, 140, 174);
}

.input-role-selection {
    margin-bottom: 20px;
}

.button-signup {
    width: 100%;
}

.link-home {
    display: block;
    text-align: center;
    width: 100%;
    margin-top: 12px;
    font-size: 13px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.4);
    text-decoration: none;
}

.spinner {
    display: flex;
    justify-content: center;
    width: 100%;
    background-color: $accent;
    border-radius: 1.5rem;
    font-size: 10px;
    padding: 5px 0px;
}

:deep(.q-field__native::placeholder) {
    font-family: $sariko-font-family-secondary; 
    font-size: 12px;
    color: rgba(255, 255, 255, 0.25);
}

:deep(.q-field__native) {
    color: #ffffff; 
}

:deep(.q-field__control) {
    border-radius: 0.75rem;
}

.hint-text {
    color: rgb(255, 255, 255, 0.5)
}
</style>