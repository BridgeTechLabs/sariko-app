<template>
    <div class="join-header">
        <router-link to="/home" class="logo">
            <img src="/logo/sariko/sariko_logo_dark_bg-removebg.png" alt="SariKo" />
        </router-link>
        <h1 class="title">{{ $t('join_page.title') }}</h1>
        <div class="subtitle">{{ $t('join_page.subtitle') }}</div>
    </div>
</template>

<style lang="scss" scoped>
.join-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 6px;
}

.logo img {
    width: 96px;
    display: block;
}

.title {
    margin: 0;
    font-family: $sariko-font-family-primary;
    font-size: 24px;
    font-weight: 600;
    line-height: 1.2;
}

.subtitle {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.6);
}
</style>
