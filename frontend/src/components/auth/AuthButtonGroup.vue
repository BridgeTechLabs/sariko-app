<script>
import { mapWritableState } from 'pinia';
import { useAuthStore } from '@/stores/auth/authStore';
export default {
    computed: {
        ...mapWritableState(useAuthStore, [
            "isSignin"
        ]),

        isActive() {
            return this.$route.path === '/signin'
        }
    },

    methods: {
        onClicked(route) {
            const authStore = useAuthStore()
            // keep the auth listener handle, as the sign-out actions do
            const sub = authStore._authSub
            authStore.$reset()
            authStore._authSub = sub
            this.$router.push(`/${route}`)
        }
    },
}
</script>

<template>

    <div class="container">

        <div class="row button-group">
            <div v-on:click="onClicked('signin')" :class="{'col-6 button': true, 'button-active': isActive}">
                {{ $t('auth_page.auth_button_group.label_signin') }}
            </div>

            <div v-on:click="onClicked('signup')" :class="{'col-6 button': true, 'button-active': !isActive}">
                {{ $t('auth_page.auth_button_group.label_signout') }}
            </div>
        </div>

    </div>

</template>

<style lang="scss" scoped>

.container {
    display: flex;
    z-index: 1;
    font-family: $sariko-font-family-secondary;
    justify-content: center;
}

.button-group {
    width: 80%;
    background-color: var(--bg-main);
    padding: 3px;
    border-radius: 1.5rem;
}

.button {
    display: flex;
    justify-content: center;
    font-size: 12px;
    font-weight: 700;
    padding: 10px 20px;
    height: 100%;
    border-radius: 1.5rem;
    color: #49505c;
}

.button-active {
    background-color: $accent;
    color: #1B2A4A;
}

</style>