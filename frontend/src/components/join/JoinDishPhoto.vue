<script>
import { Camera } from 'lucide-vue-next'
import { useJoinStore } from '@/stores/join/joinStore'

// Photo cell of one dish (used by both the table and the cards).
export default {
    components: { Camera },
    props: {
        dishKey: { type: String, required: true },
        large: { type: Boolean, default: false },
    },

    data() {
        return { loading: false }
    },

    computed: {
        store() {
            return useJoinStore()
        },
        photo() {
            return this.store.photos[this.dishKey]
        },
        error() {
            return this.store.dishErrors(this.dishKey).photo
        },
    },

    methods: {
        async onPick(event) {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (!file) return
            this.loading = true
            try {
                await this.store.setPhoto(this.dishKey, file)
            } catch (key) {
                this.$q.notify({ type: 'negative', message: this.$t(typeof key === 'string' ? key : 'join_page.error_photo_type', this.store.limits), position: 'bottom' })
            } finally {
                this.loading = false
            }
        },
    },
}
</script>

<template>
    <label class="photo" :class="{ 'photo--large': large, 'photo--error': error && !photo }">
        <input type="file" accept="image/*" class="hidden-input" @change="onPick" />
        <q-spinner v-if="loading" color="amber" size="20px" />
        <img v-else-if="photo" :src="photo.url" alt="" />
        <span v-else class="empty">
            <Camera :size="large ? 22 : 18" />
            <span v-if="large">{{ $t('join_page.menu_add_photo') }}</span>
        </span>
    </label>
</template>

<style lang="scss" scoped>
.photo {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 10px;
    border: 1px dashed rgba(255, 255, 255, 0.35);
    overflow: hidden;
    cursor: pointer;
    flex-shrink: 0;
    color: rgba(255, 255, 255, 0.7);
}

.photo--large {
    width: 100%;
    height: 160px;
}

.photo--error {
    border-color: #ef4444;
    color: #ef4444;
}

.photo img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    font-size: 12px;
}

.hidden-input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
}
</style>
