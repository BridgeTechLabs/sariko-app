<script>
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';

// Round avatar: photo if `src`, else `initials`, else a blank placeholder.
// Figma sizes are 72/48/40/24; the verified seal only shows from 40px up (as in Figma).
export default {
    components: { BaseIcon },

    props: {
        src: {
            type: String,
            default: null,
        },
        initials: {
            type: String,
            default: '',
        },
        size: {
            type: Number,
            default: 48,
        },
        verified: {
            type: Boolean,
            default: false,
        },
    },

    computed: {
        boxStyle() {
            return {
                width: `${this.size}px`,
                height: `${this.size}px`,
                fontSize: `${Math.round(this.size * 0.3)}px`,
            }
        },

        // Figma: 26px seal on 72, 17 on 48, 14 on 40
        sealSize() {
            return Math.round(this.size * 0.36)
        },
    },
}
</script>

<template>
    <div class="base-avatar" :style="boxStyle">
        <img v-if="src" class="photo" :src="src" alt="" />
        <span v-else-if="initials" class="initials">{{ initials }}</span>

        <span
            v-if="verified && size >= 40"
            class="seal"
            :style="{ width: `${sealSize}px`, height: `${sealSize}px` }"
        >
            <BaseIcon name="badge-check" :size="Math.round(sealSize * 0.77)" />
        </span>
    </div>
</template>

<style scoped>
.base-avatar {
    position: relative;
    flex-shrink: 0;
    border-radius: var(--radius-full);
    background: var(--brand-gold-soft);
    color: var(--text-gold);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: var(--font-weight-bold);
    line-height: 1;
}

.photo {
    width: 100%;
    height: 100%;
    border-radius: inherit;
    object-fit: cover;
}

.seal {
    position: absolute;
    right: -2px;
    bottom: -2px;
    border-radius: var(--radius-full);
    background: var(--card);
    color: var(--brand-gold);
    display: flex;
    align-items: center;
    justify-content: center;
}
</style>
