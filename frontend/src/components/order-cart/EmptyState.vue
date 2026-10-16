<script>
import { ShoppingBag, Search } from 'lucide-vue-next';

export default {
    components: {
        ShoppingBag, Search
    }
}
</script>

<template>
    <div class="empty-state">
        <div class="empty-icon-wrapper">
            <ShoppingBag :size="44" />
        </div>
        <h2 class="empty-title">{{ $t('cart_page.empty_title') }}</h2>
        <p class="empty-subtitle">{{ $t('cart_page.empty_subtitle') }}</p>
        <q-btn class="btn-browse" dense no-caps @click="$router.push('/home')">
            <Search :size="18" style="margin-right: 8px;" />
            {{ $t('cart_page.empty_button') }}
        </q-btn>
    </div>
</template>

<style lang="scss" scoped>
.empty-state {
    min-height: calc(100vh - 100px);
    min-height: calc(100dvh - 100px);
    padding-top: 35%;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    font-family: $sariko-font-family-secondary;
}

.empty-icon-wrapper {
    width: 100px;
    height: 100px;
    border-radius: 50%;
    background: rgba($accent, 0.08);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 28px;
    color: $accent;
    opacity: 0.7;
}

.empty-title {
    font-family: $sariko-font-family-primary;
    font-size: 22px;
    font-weight: 700;
    color: white;
    margin-bottom: 8px;
}

.empty-subtitle {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.5);
    line-height: 1.5;
    max-width: 260px;
    margin-bottom: 32px;
}

.btn-browse {
    height: 48px;
    border-radius: 2rem;
    background-color: $accent;
    color: var(--bg-main);
    font-family: $sariko-font-family-secondary;
    font-size: 15px;
    font-weight: 700;
    padding: 0 32px;
}
</style>
