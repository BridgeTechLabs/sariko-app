<script>
import VerifyEmailForm from '@/components/auth/VerifyEmailForm.vue';

export default {
    name: 'VerifyEmailPage',
    components: { VerifyEmailForm }
}
</script>

<template>
    <div class="background">
        <div class="container">
            <VerifyEmailForm />
        </div>
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
    justify-content: center;
    padding: 24px 0;
}

.container {
    width: 100%;
    padding: 0 20px;
}
</style>
