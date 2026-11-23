<script>
import { X } from 'lucide-vue-next'

// The Zen partner banner just above the home footer (fixed in code, not one of the admin banners).
// X hides it for good on this device.
const DISMISS_KEY = 'sariko.zen_footer_dismissed'

export default {
    name: 'ZenFooterBanner',
    components: { X },
    data() {
        return { dismissed: localStorage.getItem(DISMISS_KEY) === '1' }
    },
    methods: {
        open() {
            window.open(import.meta.env.VITE_ZEN_URL || 'https://zenapp.expo.app/', '_blank', 'noopener,noreferrer')
        },
        dismiss() {
            this.dismissed = true
            localStorage.setItem(DISMISS_KEY, '1')
        }
    }
}
</script>

<template>
    <div v-if="!dismissed" class="zen-footer-banner">
        <img
            src="/logo/zen/zen-banner.webp"
            alt="Zen"
            draggable="false"
            class="zen-image"
            role="button"
            tabindex="0"
            @click="open"
            @keydown.enter="open"
        />
        <button
            class="zen-dismiss"
            type="button"
            :aria-label="$t('home_page.section_zen_promo.dismiss_aria')"
            @click="dismiss"
        >
            <X :size="14" />
        </button>
    </div>
</template>

<style lang="scss" scoped>
.zen-footer-banner {
    position: relative;
    margin-bottom: 16px;
}

/* Same frame as PromoCarousel: 1200 x 236, rounded. */
.zen-image {
    display: block;
    width: 100%;
    aspect-ratio: 1200 / 236;
    border-radius: 16px;
    cursor: pointer;
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
