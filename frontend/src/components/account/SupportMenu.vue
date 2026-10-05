<script>
import { FileText, Shield, Info, Truck, CreditCard, MessageCircle, ChevronRight, ExternalLink } from 'lucide-vue-next';

export default {
    components: { FileText, Shield, Info, Truck, CreditCard, MessageCircle, ChevronRight, ExternalLink },

    computed: {
        supportMailto() {
            return 'mailto:support@sariko.store?subject=Sariko%20Support'
        }
    }
}
</script>

<template>
    <div>
        <div class="section-title">{{ $t('account_page.section_title_support') }}</div>
        <div class="menu-group">
            <a :href="supportMailto" class="menu-item">
                <div class="menu-icon"><MessageCircle size="18" /></div>
                <span class="menu-label">{{ $t('account_page.menu_label_contact_support') }}</span>
                <ExternalLink size="14" class="menu-arrow" />
            </a>

            <a href="https://buyerdox.sariko.store/" target="_blank" class="menu-item">
                <div class="menu-icon"><FileText size="18" /></div>
                <span class="menu-label">{{ $t('account_page.menu_label_terms') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </a>

            <a href="/docs/privacy-policy.html" target="_blank" class="menu-item">
                <div class="menu-icon"><Shield size="18" /></div>
                <span class="menu-label">{{ $t('account_page.menu_label_privacy') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </a>

            <a href="/docs/sariko_shipping_policy.html" target="_blank" class="menu-item">
                <div class="menu-icon"><Truck size="18" /></div>
                <span class="menu-label">{{ $t('account_page.menu_label_shipping') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </a>

            <a href="/docs/sariko_payment_methods.html" target="_blank" class="menu-item">
                <div class="menu-icon"><CreditCard size="18" /></div>
                <span class="menu-label">{{ $t('account_page.menu_label_payment_methods') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </a>

            <a href="/docs/about.html" target="_blank" class="menu-item">
                <div class="menu-icon"><Info size="18" /></div>
                <span class="menu-label">{{ $t('account_page.menu_label_about') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </a>
        </div>
        <div class="app-version">{{ $t('account_page.app_version') }}</div>
    </div>
</template>

<style scoped>
.section-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
    padding-left: 4px;
}

.menu-group {
    background: rgb(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
}

.menu-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    cursor: pointer;
    text-decoration: none;
    color: var(--text-primary);
    transition: background 0.15s ease;
}

.menu-item:not(:last-child) {
    /* border-bottom: 1px solid rgba(255, 255, 255, 0.05); */
}

.menu-item:hover {
    background: var(--bg-card-hover);
}

.menu-icon {
    width: 24px;
    height: 24px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.05);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
    flex-shrink: 0;
}

.menu-label {
    flex: 1;
    font-size: 14px;
    font-weight: 500;
}

.menu-arrow {
    color: var(--text-muted);
}

.app-version {
    margin-top: 12px;
    text-align: center;
    font-size: 11px;
    color: var(--text-muted);
    letter-spacing: 0.3px;
}
</style>
