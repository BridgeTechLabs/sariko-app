<script>
import LanguageSwitcher from '@/components/shared/LanguageSwitcher.vue';

export default {
    components: { LanguageSwitcher },

    methods: {
        onClickedToHome() {
            this.$router.push('/home')
        }
    }
}
</script>

<template>

    <div class="header">
        <!-- Guests have no Account > Language page, so they switch here -->
        <div class="lang">
            <LanguageSwitcher />
        </div>

        <div v-on:click="onClickedToHome" class="container">
            <div class="logo">
                <q-img
                ratio="1"
                src="/logo/sariko/sariko_logo_dark_bg-removebg.png"
                />
            </div>

            <div class="logo-subtitle">
                {{ $t('auth_page.subtitle_text_header') }}
            </div>
        </div>
    </div>

</template>

<style lang="scss" scoped>

.header {
    position: relative;
}

.lang {
    position: absolute;
    top: -38px;
    right: 16px;
    z-index: 2;
    // The pill uses the app theme's text colour; the auth page is always dark.
    --text-primary: #fff;
}

.container {
    display: flex;
    flex-direction: column;
    align-items: center;
}

.logo {
    width: 40%;
}

.logo-subtitle {
    margin-top: 20px;
    font-family: $sariko-font-family-secondary;
    font-weight: 700;
    font-size: 12px;
    color:rgb(122, 140, 174);
    z-index: 1;
}

</style>