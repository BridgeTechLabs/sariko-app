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
        <header class="top">
            <img class="logo-small" src="/logo/sariko/sariko_logo_dark_bg-removebg.png" alt="SariKo" />
            <LanguageSwitcher class="lang" />
        </header>

        <main class="main">
            <section class="hero">
                <img class="logo" src="/logo/sariko/sariko_logo_dark_bg-removebg.png" alt="" />
                <span class="badge">{{ $t('coming_soon_page.badge') }}</span>
                <i18n-t keypath="coming_soon_page.title" tag="h1" class="title">
                    <template #country><em>{{ $t('coming_soon_page.country') }}</em></template>
                </i18n-t>
                <p class="sub">{{ $t('coming_soon_page.sub') }}</p>
                <div v-if="launchDate" class="date">{{ $t('coming_soon_page.date_label') }} <b>{{ launchDate }}</b></div>
            </section>

            <section class="card">
                <h2>{{ $t('coming_soon_page.seller_title') }}</h2>
                <p>{{ $t('coming_soon_page.seller_text') }}</p>
                <router-link to="/signin" class="btn primary">{{ $t('coming_soon_page.signin') }}</router-link>
                <router-link to="/join" class="btn ghost">{{ $t('coming_soon_page.join') }}</router-link>
            </section>
        </main>

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
// Layout and sizes follow docs/dev/prelaunch/mockup (2026-10-22), on the /join navy instead of #040A14.
.coming-soon {
    position: relative;
    z-index: 0;  // own stacking context: the ::before layer below paints over the app's background, under this content
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    min-height: 100dvh;
    width: min(1040px, 100vw);  // wider than the app's 800px column, like the mockup; centred over it
    align-self: center;
    padding: 0 20px;
    color: #fff;
    font-family: $sariko-font-family-secondary;
}

// Navy behind the whole viewport too: on desktop the app column is 800px wide on the app's darker background.
.coming-soon::before {
    content: '';
    position: fixed;
    inset: 0;
    z-index: -1;
    background-color: #121b2f;
}

.top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
}

.logo-small {
    height: 36px;
}

.lang {
    --text-primary: #fff;  // the pill uses the theme text colour; this page is always dark
}

.main {
    flex: 1;
    display: grid;
    gap: 24px;
    align-content: center;
    padding: 8px 0 12px;
}

.hero {
    display: grid;
    justify-items: center;
    gap: 12px;
    text-align: center;
}

.logo {
    width: 112px;
    height: 112px;
    object-fit: contain;
}

.badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border: 1px solid rgba(250, 204, 21, 0.35);
    border-radius: 999px;
    background: rgba(250, 204, 21, 0.12);
    color: #facc15;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.02em;
}

.badge::before {
    content: '';
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #facc15;
    box-shadow: 0 0 0 4px rgba(250, 204, 21, 0.18);
}

.title {
    margin: 0;
    max-width: 22ch;
    font-family: $sariko-font-family-secondary;
    font-size: 28px;
    font-weight: 800;
    line-height: 1.25;
    letter-spacing: normal;
}

.title em {
    font-style: normal;
    color: #facc15;
}

.sub {
    margin: 0;
    max-width: 46ch;
    font-size: 15px;
    line-height: 1.6;
    color: rgba(255, 255, 255, 0.6);
}

.date {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    border: 1px solid #374151;
    border-radius: 12px;
    background: #1f2940;
    font-weight: 600;
}

.date b {
    font-size: 18px;
    color: #facc15;
}

.card {
    display: grid;
    gap: 12px;
    padding: 20px;
    border: 1px solid #374151;
    border-radius: 16px;
    background: #111620;
}

.card h2 {
    margin: 0;
    font-family: $sariko-font-family-secondary;
    font-size: 17px;
    font-weight: 700;
    line-height: 1.4;
}

.card p {
    margin: 0;
    font-size: 14px;
    line-height: 1.55;
    color: rgba(255, 255, 255, 0.6);
}

.btn {
    display: block;
    padding: 13px 16px;
    border-radius: 12px;
    font-size: 15px;
    font-weight: 700;
    text-align: center;
    text-decoration: none;
}

.btn.primary {
    background: #facc15;
    color: #121b2f;
}

.btn.ghost {
    border: 1px solid #374151;
    color: #fff;
}

.legal {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    align-items: center;
    gap: 2px 10px;
    padding: 12px 0;
    border-top: 1px solid #374151;
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

@media (min-width: 900px) {
    .main {
        grid-template-columns: 1.3fr 1fr;
        align-items: center;
        gap: 48px;
    }

    .hero {
        justify-items: start;
        text-align: left;
    }

    .logo {
        width: 132px;
        height: 132px;
    }

    .title {
        font-size: 40px;
    }
}
</style>
