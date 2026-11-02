<script>
import ForgotPasswordForm from '@/components/auth/ForgotPasswordForm.vue';

export default {
    name: 'ForgotPasswordPage',
    components: { ForgotPasswordForm }
}
</script>

<template>
    <div class="background">
        <q-img class="logo" ratio="1" src="/logo/sariko/sariko_logo_dark_bg-removebg.png" />
        <div class="spacer-top"></div>
        <div class="container">
            <ForgotPasswordForm />
        </div>
        <div class="spacer-bottom"></div>
    </div>
</template>

<style scoped>
.background {
    min-height: 100vh;
    min-height: 100dvh;
    background-color: #121b2f;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 0;
}

.logo {
    width: 40%;
    flex-shrink: 0;
}

/* Content sits around the upper quarter of the screen, not dead center (Jack 02/11). */
.spacer-top {
    flex: 1;
}

.spacer-bottom {
    flex: 3;
}

.container {
    width: 100%;
    padding: 0 20px;
}
</style>
