<script>
import { ChevronRight, X } from 'lucide-vue-next'

const DISMISS_KEY = 'sariko.zen_promo_dismissed_version'
// Bump this when banner copy/visual changes and you want all users to see it again.
const BANNER_VERSION = '1'

export default {
    name: 'ZenPromoBanner',
    components: { ChevronRight, X },
    data() {
        return {
            dismissed: false
        }
    },
    mounted() {
        this.dismissed = localStorage.getItem(DISMISS_KEY) === BANNER_VERSION
    },
    methods: {
        openZen() {
            window.open('https://zenapp.expo.app/', '_blank', 'noopener,noreferrer')
        },
        dismiss() {
            this.dismissed = true
            localStorage.setItem(DISMISS_KEY, BANNER_VERSION)
        }
    }
}
</script>

<template>
    <div
        v-if="!dismissed"
        class="zen-banner"
        role="button"
        tabindex="0"
        @click="openZen"
        @keydown.enter="openZen"
    >
        <img
            src="/logo/zen/zen-logo-blue-bg.jpg"
            alt="Zen"
            class="zen-logo"
        />

        <div class="zen-text">
            <span class="zen-title">{{ $t('home_page.section_zen_promo.title') }}</span>
            <span class="zen-subtitle">{{ $t('home_page.section_zen_promo.subtitle') }}</span>
        </div>

        <button
            class="zen-dismiss"
            type="button"
            :aria-label="$t('home_page.section_zen_promo.dismiss_aria')"
            @click.stop="dismiss"
        >
            <X :size="14" />
        </button>

        <ChevronRight :size="20" class="zen-chevron" />
    </div>
</template>

<style lang="scss" scoped>
.zen-banner {
    position: relative;
    width: 100%;
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

.zen-dismiss {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: rgba(0, 0, 0, 0.25);
    color: rgba(255, 255, 255, 0.85);
    cursor: pointer;

    &:hover {
        background: rgba(0, 0, 0, 0.4);
        color: #fff;
    }
}
</style>
