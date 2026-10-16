<script>
import { UtensilsCrossed } from 'lucide-vue-next';

export default {
    components: { UtensilsCrossed }
}
</script>

<template>
    <div class="menu-empty">
        <UtensilsCrossed :size="36" class="menu-empty__icon" />
        <p class="menu-empty__text">{{ $t('seller_page.menu_empty_category') }}</p>
    </div>
</template>

<style lang="scss" scoped>
.menu-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 300px;
    text-align: center;

    &__icon {
        color: $accent;
        opacity: 0.45;
        margin-bottom: 14px;
    }

    &__text {
        font-family: $sariko-font-family-secondary;
        font-size: 14px;
        color: rgba(255, 255, 255, 0.4);
        margin: 0;
    }
}
</style>
