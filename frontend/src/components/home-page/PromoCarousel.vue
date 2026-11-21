<script>
import { mapState, mapActions } from 'pinia'
import { X } from 'lucide-vue-next'
import { useHomeStore } from '@/stores/homeStore'

// Holds the ids of the banners shown when the buyer pressed X: a new list of banners shows the carousel again.
const DISMISS_KEY = 'sariko.zen_promo_dismissed_version'

export default {
    name: 'PromoCarousel',
    components: { X },
    data() {
        return {
            slide: null,
            broken: [],                                     // ids whose image failed to load
            dismissedIds: localStorage.getItem(DISMISS_KEY)  // null = never dismissed
        }
    },
    computed: {
        ...mapState(useHomeStore, ['promoBanners']),
        ids() {
            return (this.promoBanners || []).map(b => b.id).join(',')
        },
        shown() {
            return (this.promoBanners || []).filter(b => !this.broken.includes(b.id))
        },
        // A buyer who dismissed it once gets no placeholder: it would flash and vanish on every visit.
        loading() {
            return this.promoBanners === null && this.dismissedIds === null
        },
        visible() {
            return this.shown.length > 0 && this.dismissedIds !== this.ids
        }
    },
    watch: {
        // immediate: back on the home page the store already holds the list from the last visit
        promoBanners: {
            handler(banners) {
                // Load every image now so a dead one leaves before its turn (and the dots count only the live ones).
                for (const b of banners || []) {
                    const img = new Image()
                    img.onerror = () => this.broken.push(b.id)
                    img.src = b.image_url
                }
            },
            immediate: true
        },
        shown: {
            handler(list) {
                if (!list.some(b => b.id === this.slide)) this.slide = list[0]?.id ?? null
            },
            immediate: true
        }
    },
    created() {
        this.fetchPromoBanners()
    },
    methods: {
        ...mapActions(useHomeStore, ['fetchPromoBanners']),
        open(banner) {
            window.open(banner.link_url, '_blank', 'noopener,noreferrer')
        },
        dismiss() {
            this.dismissedIds = this.ids
            localStorage.setItem(DISMISS_KEY, this.ids)
        }
    }
}
</script>

<template>
    <q-skeleton v-if="loading" animation="pulse" class="promo-skeleton" />

    <div v-else-if="visible" class="promo-carousel">
        <q-carousel
            v-model="slide"
            swipeable
            animated
            infinite
            :autoplay="shown.length > 1 && 5000"
            class="carousel"
        >
            <q-carousel-slide v-for="b in shown" :key="b.id" :name="b.id" class="slide">
                <img
                    :src="b.image_url"
                    :alt="b.alt"
                    draggable="false"
                    class="promo-banner"
                    role="button"
                    tabindex="0"
                    @click="open(b)"
                    @keydown.enter="open(b)"
                />
            </q-carousel-slide>
        </q-carousel>

        <div v-if="shown.length > 1" class="promo-dots">
            <button
                v-for="(b, i) in shown"
                :key="b.id"
                type="button"
                class="promo-dot"
                :class="{ active: slide === b.id }"
                :aria-label="b.alt || String(i + 1)"
                @click="slide = b.id"
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

/* Every banner is 1200 x 236 (the admin app refuses other shapes), so its baked-in text is never cropped. */
.carousel {
    height: auto;
    aspect-ratio: 1200 / 236;
    border-radius: 16px;
    background: transparent;
}

.promo-skeleton {
    width: 100%;
    height: auto;
    aspect-ratio: 1200 / 236;
    border-radius: 16px;
}

.slide {
    padding: 0;
}

.promo-banner {
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
