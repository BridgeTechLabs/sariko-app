<script>
import { X } from 'lucide-vue-next'
import ZenPromoBanner from '@/components/home-page/ZenPromoBanner.vue'

const DISMISS_KEY = 'sariko.zen_promo_dismissed_version'
// Bump VITE_ZEN_BANNER_VERSION (and rebuild) to re-show the promos to users who dismissed them.
const BANNER_VERSION = import.meta.env.VITE_ZEN_BANNER_VERSION || '3'

export default {
    name: 'PromoCarousel',
    components: { X, ZenPromoBanner },
    props: {
        showZen: { type: Boolean, default: false }
    },
    data() {
        return {
            slide: 'tambayan',
            dismissed: false
        }
    },
    mounted() {
        this.dismissed = localStorage.getItem(DISMISS_KEY) === BANNER_VERSION
    },
    methods: {
        openTambayan() {
            window.open(import.meta.env.VITE_TAMBAYAN_URL || 'https://tambayan.sariko.store', '_blank', 'noopener,noreferrer')
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
            <q-carousel-slide name="tambayan" class="slide">
                <img
                    src="/logo/tambayan/tambayan-banner.webp"
                    alt="SariKo Tambayan"
                    draggable="false"
                    class="tambayan-banner"
                    role="button"
                    tabindex="0"
                    @click="openTambayan"
                    @keydown.enter="openTambayan"
                />
            </q-carousel-slide>

            <q-carousel-slide v-if="showZen" name="zen" class="slide">
                <ZenPromoBanner />
            </q-carousel-slide>
        </q-carousel>

        <div v-if="showZen" class="promo-dots">
            <button
                v-for="name in ['tambayan', 'zen']"
                :key="name"
                type="button"
                class="promo-dot"
                :class="{ active: slide === name }"
                :aria-label="name === 'zen' ? 'Zen' : 'SariKo Tambayan'"
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

/* Height follows the Tambayan image (1200 x 236) so its baked-in text is never cropped. */
.carousel {
    height: auto;
    aspect-ratio: 1200 / 236;
    border-radius: 16px;
    background: transparent;
}

.slide {
    padding: 0;
}

.tambayan-banner {
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
