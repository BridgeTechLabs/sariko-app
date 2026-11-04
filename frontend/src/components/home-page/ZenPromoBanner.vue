<script>
import { ChevronRight } from 'lucide-vue-next'

// A slide of PromoCarousel, which owns the dismiss button.
export default {
    name: 'ZenPromoBanner',
    components: { ChevronRight },
    methods: {
        openZen() {
            window.open(import.meta.env.VITE_ZEN_URL || 'https://zenapp.expo.app/', '_blank', 'noopener,noreferrer')
        }
    }
}
</script>

<template>
    <div
        class="zen-banner"
        role="button"
        tabindex="0"
        @click="openZen"
        @keydown.enter="openZen"
    >
        <img
            src="/logo/zen/zen-logo-blue-bg.jpg"
            alt="Zen"
            draggable="false"
            class="zen-logo"
        />

        <div class="zen-text">
            <span class="zen-title">{{ $t('home_page.section_zen_promo.title') }}</span>
            <span class="zen-subtitle">{{ $t('home_page.section_zen_promo.subtitle') }}</span>
        </div>

        <ChevronRight :size="20" class="zen-chevron" />
    </div>
</template>

<style lang="scss" scoped>
.zen-banner {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border: none;
    border-radius: 16px;
    background: linear-gradient(135deg, #0b2a6b 0%, #1f4fd1 100%);
    color: #fff;
    cursor: pointer;
    text-align: left;
    transition: transform 0.15s ease, box-shadow 0.15s ease;

    &:active {
        transform: scale(0.98);
    }
}

.zen-logo {
    width: 44px;
    height: 44px;
    border-radius: 10px;
    object-fit: cover;
    flex-shrink: 0;
}

.zen-text {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    padding-right: 16px;
}

.zen-title {
    font-family: $sariko-font-family-secondary;
    font-weight: 700;
    font-size: 14px;
    line-height: 1.2;
    color: #fff;
}

.zen-subtitle {
    font-family: $sariko-font-family-secondary;
    font-weight: 500;
    font-size: 11px;
    line-height: 1.3;
    color: rgba(255, 255, 255, 0.78);
    margin-top: 2px;
}

.zen-chevron {
    position: absolute;
    bottom: 8px;
    right: 8px;
    color: rgba(255, 255, 255, 0.85);
}
</style>
