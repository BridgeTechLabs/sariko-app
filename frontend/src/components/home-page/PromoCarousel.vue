<script>
import { X } from 'lucide-vue-next'
import ZenPromoBanner from '@/components/home-page/ZenPromoBanner.vue'

const DISMISS_KEY = 'sariko.zen_promo_dismissed_version'
// Bump VITE_ZEN_BANNER_VERSION (and rebuild) to re-show the promos to users who dismissed them.
const BANNER_VERSION = import.meta.env.VITE_ZEN_BANNER_VERSION || '2'

export default {
    name: 'PromoCarousel',
    components: { X, ZenPromoBanner },
    props: {
        showZen: { type: Boolean, default: false }
    },
    data() {
        return {
            slide: this.showZen ? 'zen' : 'pangea',
            dismissed: false
        }
    },
    mounted() {
        this.dismissed = localStorage.getItem(DISMISS_KEY) === BANNER_VERSION
    },
    methods: {
        openPangea() {
            window.open(import.meta.env.VITE_PANGEA_URL || 'https://game.pangea.town', '_blank', 'noopener,noreferrer')
        },
        dismiss() {
            this.dismissed = true
            localStorage.setItem(DISMISS_KEY, BANNER_VERSION)
        }
    }
}
</script>

<template>
    <div v-if="!dismissed" class="promo-carousel">
        <q-carousel
            v-model="slide"
            swipeable
            animated
            infinite
            :autoplay="showZen && 5000"
            class="carousel"
        >
            <q-carousel-slide v-if="showZen" name="zen" class="slide">
                <ZenPromoBanner />
            </q-carousel-slide>

            <q-carousel-slide name="pangea" class="slide">
                <img
                    src="/logo/pangea/pangea-town-banner.webp"
                    alt="PangeaTown"
                    draggable="false"
                    class="pangea-banner"
                    role="button"
                    tabindex="0"
                    @click="openPangea"
                    @keydown.enter="openPangea"
                />
            </q-carousel-slide>
        </q-carousel>

        <div v-if="showZen" class="promo-dots">
            <button
                v-for="name in ['zen', 'pangea']"
                :key="name"
                type="button"
                class="promo-dot"
                :class="{ active: slide === name }"
                :aria-label="name === 'zen' ? 'Zen' : 'PangeaTown'"
                @click="slide = name"
            />
        </div>

        <button
            class="promo-dismiss"
            type="button"
            :aria-label="$t('home_page.section_promo.dismiss_aria')"
            @click="dismiss"
        >
            <X :size="14" />
        </button>
    </div>
</template>

<style lang="scss" scoped>
.promo-carousel {
    position: relative;
}

/* Height follows the PangeaTown image (2904 x 570) so its baked-in text is never cropped. */
.carousel {
    height: auto;
    aspect-ratio: 2904 / 570;
    border-radius: 16px;
    background: transparent;
}

.slide {
    padding: 0;
}

.pangea-banner {
    display: block;
    width: 100%;
    height: 100%;
    border-radius: 16px;
    cursor: pointer;
}

.promo-dots {
    display: flex;
    justify-content: center;
    gap: 6px;
    margin-top: 6px;
}

.promo-dot {
    width: 6px;
    height: 6px;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.3);
    cursor: pointer;

    &.active {
        background: rgba(255, 255, 255, 0.85);
    }
}

.promo-dismiss {
    position: absolute;
    top: 6px;
    right: 6px;
    z-index: 2;
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
