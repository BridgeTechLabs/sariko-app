<script>
import { Monitor } from 'lucide-vue-next'

export default {
    components: { Monitor },

    methods: {
        async copyLink() {
            try {
                await navigator.clipboard.writeText(window.location.origin + '/join')
                this.$q.notify({ type: 'positive', message: this.$t('join_page.tip_copied'), position: 'bottom', timeout: 1500 })
            } catch {
                this.$q.notify({ type: 'warning', message: window.location.origin + '/join', position: 'bottom', timeout: 4000 })
            }
        },
    },
}
</script>

<template>
    <div v-if="!$q.screen.gt.sm" class="tip">
        <Monitor :size="18" class="icon" />
        <div class="text">
            <div class="tip-title">{{ $t('join_page.tip_title') }}</div>
            <div class="tip-body">{{ $t('join_page.tip_body') }}</div>
        </div>
        <q-btn no-caps unelevated dense class="btn-copy" :label="$t('join_page.tip_copy')" @click="copyLink" />
    </div>
</template>

<style lang="scss" scoped>
.tip {
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(245, 166, 35, 0.1);
    border: 1px solid rgba(245, 166, 35, 0.3);
    border-radius: 12px;
    padding: 10px 12px;
}

.icon {
    flex-shrink: 0;
    color: #f5a623;
}

.text {
    flex: 1;
    font-size: 12px;
    line-height: 1.45;
}

.tip-title {
    font-weight: 700;
}

.tip-body {
    color: rgba(255, 255, 255, 0.65);
}

.btn-copy {
    flex-shrink: 0;
    padding: 4px 10px;
    background: #f5a623;
    color: #121b2f;
    font-weight: 700;
    border-radius: 8px;
}
</style>
