<script>
import VerifyEmailForm from '@/components/auth/VerifyEmailForm.vue';

export default {
    name: 'VerifyEmailPage',
    components: { VerifyEmailForm }
}
</script>

<template>
    <div class="background">
        <q-img class="logo" ratio="1" src="/logo/sariko/sariko_logo_dark_bg-removebg.png" />
        <div class="container">
            <VerifyEmailForm />
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
    margin-bottom: 20px;
}

/* Logo + content sit together near the top; this pushes the rest of the
   screen's empty space below them instead of centering (Jack 02/11). */
.spacer-bottom {
    flex: 1;
}

.container {
    width: 100%;
    padding: 0 20px;
}
</style>
