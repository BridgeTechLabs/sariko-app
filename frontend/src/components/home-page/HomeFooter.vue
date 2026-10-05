<template>
    <footer class="home-footer">
        <nav class="footer-links">
            <a href="https://buyerdox.sariko.store/" target="_blank" rel="noopener">{{ $t('account_page.menu_label_terms') }}</a>
            <a href="/docs/privacy-policy.html" target="_blank">{{ $t('account_page.menu_label_privacy') }}</a>
            <a href="/docs/sariko_shipping_policy.html" target="_blank">{{ $t('account_page.menu_label_shipping') }}</a>
            <a href="/docs/sariko_payment_methods.html" target="_blank">{{ $t('account_page.menu_label_payment_methods') }}</a>
            <a href="/docs/about.html" target="_blank">{{ $t('account_page.menu_label_about') }}</a>
        </nav>

        <div class="company-info">
            <div class="company-name">Công ty TNHH ZEN TECH ASIA</div>
            <div>{{ $t('home_page.section_footer.label_tax_code') }}: 0316852554</div>
            <div>{{ $t('home_page.section_footer.label_address') }}: 195/3 Điện Biên Phủ, P. 15, Q. Bình Thạnh, Tp. Hồ Chí Minh</div>
            <div>{{ $t('home_page.section_footer.label_email') }}: <a href="mailto:info@sariko.store">info@sariko.store</a></div>
        </div>

        <a href="https://online.gov.vn/nen-tang/1929fbb4-3ace-4ebf-920e-1520195f0f37" target="_blank" rel="noopener" title="Đã xác nhận với Bộ Công Thương" class="moit-badge">
            <img src="https://fileserver.online.gov.vn/uploads/Resources/iconxacnhan/DaThongBao.png" alt="Đã xác nhận" />
        </a>
    </footer>
</template>

<style scoped>
.home-footer {
    padding-top: 16px;
    border-top: 1px solid var(--divider);
    font-size: 11px;
    line-height: 1.6;
    color: var(--text-muted);
}

.footer-links {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
    margin-bottom: 12px;
}

.footer-links a {
    color: var(--text-secondary);
    text-decoration: none;
}

.company-info a {
    color: inherit;
}

.company-name {
    font-weight: 600;
    color: var(--text-secondary);
}

.moit-badge {
    display: block;
    width: fit-content;
    margin-top: 12px;
}

.moit-badge img {
    height: 44px;
    display: block;
}
</style>
