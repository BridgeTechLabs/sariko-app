// Smoke tests of the main flows on DEV after each deploy (docs/dev/e2e-smoke).
// Run: cd tests/e2e && npm ci && npx playwright test
// Env: DEV_BUYER_EMAIL / _PASSWORD, DEV_SELLER_*, DEV_ADMIN_* (values in .config/sariko/dummy_creds);
// BASE_URL, API_URL, ADMIN_URL override the DEV hosts (e.g. a local app on http://localhost:8081).
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
    timeout: 60_000,
    expect: { timeout: 10_000 },
    workers: 1,          // the flows share one buyer cart and one seller
    use: { trace: 'retain-on-failure', screenshot: 'only-on-failure' },
    projects: [
        {
            name: 'app',
            testMatch: 'app.spec.js',
            use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, baseURL: process.env.BASE_URL || 'https://app-dev.sariko.store' },
        },
        {
            name: 'admin',
            testMatch: 'admin.spec.js',
            use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 }, baseURL: process.env.ADMIN_URL || 'https://admin-dev.sariko.store' },
        },
    ],
})
