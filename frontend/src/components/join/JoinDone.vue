<script>
import { CircleCheck } from 'lucide-vue-next'
import { useJoinStore } from '@/stores/join/joinStore'

export default {
    components: { CircleCheck },

    data() {
        return { supportEmail: 'support' + '@' + 'sariko.store' }
    },

    computed: {
        store() {
            return useJoinStore()
        },
    },
}
</script>

<template>
    <div class="done">
        <CircleCheck :size="48" class="icon" />
        <div class="title">{{ $t('join_page.done_title') }}</div>
        <div class="ref-label">{{ $t('join_page.done_reference') }}</div>
        <div class="ref">{{ store.reference }}</div>
        <div class="text">{{ $t('join_page.done_text', { ...store.limits, email: store.form.email.trim() }) }}</div>
        <div class="text">
            {{ $t('join_page.done_contact') }}
            <a :href="`mailto:${supportEmail}`" class="join-link">{{ supportEmail }}</a>
        </div>
        <router-link to="/home" class="join-link">{{ $t('join_page.done_home') }}</router-link>
    </div>
</template>

<style lang="scss" scoped>
.done {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 10px;
    background: #1f2940;
    border-radius: 16px;
    padding: 28px 20px;
    max-width: 520px;
    margin: 0 auto;
}

.icon {
    color: #10b981;
}

.title {
    font-family: $sariko-font-family-primary;
    font-size: 20px;
    font-weight: 600;
}

.ref-label {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.6);
}

.ref {
    font-family: monospace;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 2px;
    color: #f5a623;
}

.text {
    font-size: 13px;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.8);
}
</style>
