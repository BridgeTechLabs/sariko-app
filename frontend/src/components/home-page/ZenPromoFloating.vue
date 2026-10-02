<script>
import { X } from 'lucide-vue-next'

const DISMISS_KEY = 'sariko.zen_promo_floating_dismissed_version'
const FLOATING_VERSION = '1'

export default {
    name: 'ZenPromoFloating',
    components: { X },
    data() {
        return {
            dismissed: false
        }
    },
    mounted() {
        this.dismissed = localStorage.getItem(DISMISS_KEY) === FLOATING_VERSION
    },
    methods: {
        openZen() {
            window.open(import.meta.env.VITE_ZEN_URL || 'https://link.zenapppro.com/online', '_blank', 'noopener,noreferrer')
        },
        dismiss() {
            this.dismissed = true
            localStorage.setItem(DISMISS_KEY, FLOATING_VERSION)
        }
    }
}
</script>

<template>
    <div v-if="!dismissed" class="zen-floating-wrapper">

        <div
            class="zen-floating"
            role="button"
            tabindex="0"
            :aria-label="$t('home_page.section_zen_promo.title')"
            @click="openZen"
            @keydown.enter="openZen"
        >
            <img
                src="/logo/zen/zen-logo-blue-bg.jpg"
                alt="Zen"
                class="zen-floating-logo"
            />

            <button
                class="zen-floating-dismiss"
                type="button"
                :aria-label="$t('home_page.section_zen_promo.dismiss_aria')"
                @click.stop="dismiss"
            >
                <X :size="12" />
            </button>
        </div>

        <svg
            class="zen-floating-arc"
            viewBox="0 0 130 130"
            aria-hidden="true"
        >
            <defs>
                <path
                    id="zen-arc-path"
                    d="M 20,65 A 45, 45 0 0 0 110,65"
                    fill="none"
                />
            </defs>
            <text class="zen-arc-text">
                <textPath
                    href="#zen-arc-path"
                    side="right"
                    startOffset="50%"
                    text-anchor="middle"
                >
                    {{ $t('home_page.section_zen_promo.pill_title') }}
                </textPath>
            </text>
        </svg>

    </div>
</template>

<style lang="scss" scoped>
.zen-floating-wrapper {
    position: fixed;
    right: 16px;
    top: 50%;
    transform: translateY(-50%);
    width: 60px;
    height: 60px;
    z-index: 1000;
}

.zen-floating {
    position: relative;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    cursor: pointer;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35), 0 0 0 2px rgba(31, 79, 209, 0.4);
    transition: transform 0.15s ease;
    animation: zen-pulse 2.5s ease-in-out infinite;

    &:active {
        transform: scale(0.94);
    }
}

.zen-floating-logo {
    width: 100%;
    height: 100%;
    border-radius: 50%;
    object-fit: cover;
    display: block;
}

.zen-floating-dismiss {
    position: absolute;
    top: -8px;
    right: -8px;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: #2a3245;
    color: rgba(255, 255, 255, 0.9);
    cursor: pointer;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.45);
    z-index: 1;
    transition: background 0.15s ease, transform 0.15s ease;

    &:hover {
        background: #3a4258;
        color: #fff;
    }

    &:active {
        transform: scale(0.9);
    }
}

.zen-floating-arc {
    position: absolute;
    width: 130px;
    height: 130px;
    left: -35px;
    top: -35px;
    pointer-events: none;
    overflow: visible;
    z-index: 2;
}

.zen-arc-text {
    font-family: $sariko-font-family-secondary;
    font-size: 11px;
    font-weight: 700;
    fill: #fff;
    letter-spacing: 0.02em;
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.7));
}

@keyframes zen-pulse {
    0%, 100% {
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35), 0 0 0 2px rgba(31, 79, 209, 0.4);
    }
    50% {
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.4), 0 0 0 6px rgba(31, 79, 209, 0.15);
    }
}
</style>
