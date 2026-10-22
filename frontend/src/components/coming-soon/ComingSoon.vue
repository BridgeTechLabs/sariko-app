<script>
import LanguageSwitcher from '@/components/shared/LanguageSwitcher.vue'
import { apiLaunch } from '@/apis/launch/apiLaunch'

export default {
    components: { LanguageSwitcher },

    data() {
        return { launchDate: null }
    },

    async created() {
        const date = (await apiLaunch.get()).launch_date   // "YYYY-MM-DD" or null (no date announced)
        this.launchDate = date && date.split('-').reverse().join('/')
    },
}
</script>

<template>
    <div class="coming-soon">
        <div class="lang">
            <LanguageSwitcher />
        </div>

        <div class="main">
            <img class="logo" src="/logo/sariko/sariko_logo_dark_bg-removebg.png" alt="SariKo" />
            <div class="heading">
                <h1 class="title">{{ $t('coming_soon_page.title') }}</h1>
                <div v-if="launchDate" class="date">{{ $t('coming_soon_page.opening_date', { date: launchDate }) }}</div>
            </div>
            <p class="intro">{{ $t('coming_soon_page.intro') }}</p>
            <div class="seller-card">
                <div class="seller-title">{{ $t('coming_soon_page.seller_title') }}</div>
                <router-link to="/signin" class="btn-primary">{{ $t('coming_soon_page.seller_signin') }}</router-link>
                <router-link to="/join" class="btn-link">{{ $t('coming_soon_page.seller_join') }}</router-link>
            </div>
        </div>

        <!-- This page stands in for the home page, so it keeps the operator details a marketplace must publish. -->
        <footer class="legal">
            <span>Công ty TNHH Zen Tech Asia · {{ $t('home_page.section_footer.label_tax_code') }} 0316852554</span>
            <span>
                <a href="https://buyerdox.sariko.store/" target="_blank" rel="noopener">{{ $t('account_page.menu_label_terms') }}</a>
                ·
                <a href="/docs/privacy-policy.html" target="_blank">{{ $t('account_page.menu_label_privacy') }}</a>
            </span>
            <a href="https://online.gov.vn/nen-tang/1929fbb4-3ace-4ebf-920e-1520195f0f37" target="_blank" rel="noopener" title="Đã xác nhận với Bộ Công Thương">
                <img class="moit-badge" src="https://fileserver.online.gov.vn/uploads/Resources/iconxacnhan/DaThongBao.png" alt="Đã xác nhận" />
            </a>
        </footer>
    </div>
</template>

<style lang="scss" scoped>
.coming-soon {
    position: relative;
    z-index: 0;  // own stacking context: the ::before layer below paints over the app's background, under this content
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    min-height: 100dvh;
    padding: 16px 16px 12px;
    background-color: #121b2f;  // the /join navy
    color: #fff;
    font-family: $sariko-font-family-secondary;
    text-align: center;
}

// Navy behind the whole viewport too: on desktop the app column is 800px wide on the app's darker background.
.coming-soon::before {
    content: '';
    position: fixed;
    inset: 0;
    z-index: -1;
    background-color: #121b2f;
}

.lang {
    align-self: flex-end;
    --text-primary: #fff;  // the pill uses the theme text colour; this page is always dark
}

.main {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-evenly;
    align-items: center;
    gap: 12px;
    width: 100%;
    max-width: 480px;
    margin: 0 auto;
}

.logo {
    width: 120px;
}

.title {
    margin: 0;
    font-family: $sariko-font-family-primary;
    font-size: 26px;
    font-weight: 700;
    line-height: 1.3;
    color: #fff;
}

.date {
    margin-top: 6px;
    font-size: 16px;
    font-weight: 600;
    color: #f5a623;
}

.intro {
    margin: 0;
    font-size: 14px;
    line-height: 1.6;
    color: rgba(255, 255, 255, 0.75);
}

.seller-card {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    width: 100%;
    padding: 16px;
    border-radius: 16px;
    background: #1f2940;
}

.seller-title {
    font-size: 14px;
    font-weight: 600;
}

.btn-primary {
    padding: 12px;
    border-radius: 12px;
    background: #facc15;
    color: #121b2f;
    font-weight: 700;
    text-decoration: none;
}

.btn-link {
    color: #f5a623;
    font-weight: 600;
    text-decoration: none;
}

.legal {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    align-items: center;
    gap: 2px 10px;
    margin-top: 16px;
    font-size: 11px;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.45);
}

.legal a {
    color: inherit;
}

.moit-badge {
    height: 24px;
    vertical-align: middle;
}
</style>
