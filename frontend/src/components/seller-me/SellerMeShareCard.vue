<script>
import { Copy, Check, Download } from 'lucide-vue-next'
import { mapState } from 'pinia'
import { useDashboardStore } from '@/stores/seller/dashboardStore'
import QRCode from 'qrcode'
import SectionTitle from '@/components/shared/SectionTitle.vue';

export default {
    name: 'SellerMeShareCard',

    components: { Copy, Check, Download, SectionTitle },

    data() {
        return {
            copied: false,
        }
    },

    computed: {
        ...mapState(useDashboardStore, ['sellerInfo']),

        shopUrl() {
            if (!this.sellerInfo?.slug) return null
            return `${window.location.origin}/seller/${this.sellerInfo.slug}`
        },
    },

    watch: {
        shopUrl(url) {
            if (url) this._renderQR(url)
        },
    },

    async mounted() {
        const store = useDashboardStore()
        if (!store.sellerInfo) await store.fetchSellerInfo()
        if (this.shopUrl) this._renderQR(this.shopUrl)
    },

    methods: {
        async _renderQR(url) {
            await this.$nextTick()
            const canvas = this.$refs.qrCanvas
            if (!canvas) return
            await QRCode.toCanvas(canvas, url, {
                width: 120,
                margin: 1,
                color: { dark: '#1a2540', light: '#ffffff' },
            })
        },

        async copyLink() {
            if (!this.shopUrl) return
            await navigator.clipboard.writeText(this.shopUrl)
            this.copied = true
            setTimeout(() => { this.copied = false }, 2000)
        },

        downloadQR() {
            const canvas = this.$refs.qrCanvas
            if (!canvas) return
            const link = document.createElement('a')
            link.download = `sariko-qr-${this.sellerInfo?.slug || 'store'}.png`
            link.href = canvas.toDataURL('image/png')
            link.click()
        },
    },
}
</script>

<template>
    <div>
        <SectionTitle>{{ $t('seller_me.section_title_promote') }}</SectionTitle>
        <div class="promote-card">

            <p class="promote-subtitle">{{ $t('seller_me.promote_subtitle') }}</p>

            <div class="qr-frame">
                <canvas ref="qrCanvas" class="qr-canvas" />
            </div>

            <div class="btn-row">
                <button class="btn btn-primary" @click="copyLink" :disabled="!shopUrl">
                    <Check v-if="copied" :size="15" />
                    <Copy v-else :size="15" />
                    {{ copied ? $t('seller_me.promote_copied') : $t('seller_me.promote_copy') }}
                </button>

                <button class="btn btn-secondary" @click="downloadQR" :disabled="!shopUrl">
                    <Download :size="15" />
                    {{ $t('seller_me.promote_download') }}
                </button>
            </div>

        </div>
    </div>
</template>

<style scoped>
.promote-card {
    background: rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 24px 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
}

.promote-subtitle {
    font-size: 13px;
    color: var(--text-secondary);
    margin: 0;
    line-height: 1.4;
    text-align: center;
}

.qr-frame {
    background: #ffffff;
    border-radius: 16px;
    padding: 12px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
}

.qr-canvas {
    display: block;
    border-radius: 6px;
    width: 120px !important;
    height: 120px !important;
}

.btn-row {
    display: flex;
    gap: 12px;
    width: 100%;
}

.btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-height: 44px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 600;
    font-family: 'Plus Jakarta Sans', sans-serif;
    cursor: pointer;
    transition: opacity 0.15s, transform 0.1s;
}

.btn:disabled {
    opacity: 0.4;
    cursor: default;
}

.btn-primary {
    background: var(--color-accent, #f5a623);
    color: #121b2f;
    border: none;
}

.btn-primary:hover:not(:disabled) {
    opacity: 0.9;
    transform: translateY(-1px);
}

.btn-secondary {
    background: transparent;
    color: var(--color-accent, #f5a623);
    border: 1px solid var(--color-accent, #f5a623);
}

.btn-secondary:hover:not(:disabled) {
    background: rgba(245, 166, 35, 0.08);
}
</style>
