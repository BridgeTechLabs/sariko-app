// Admin smoke on DEV at 1280 (docs/dev/e2e-smoke E2E-8).
import { test, expect } from '@playwright/test'
import { account, checkPage, refuseProd, watch } from './lib.js'

test('E2E-8 admin pages list rows', async ({ page }) => {
    const problems = watch(page)
    const { email, password } = account('ADMIN')
    await page.goto('/login')
    refuseProd(page.url())
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Password').fill(password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await page.waitForURL((u) => !u.pathname.startsWith('/login'))
    for (const path of ['/payouts', '/orders', '/seller-management']) {
        await page.goto(path)
        await expect(page.getByRole('row').nth(1), `${path} has rows`).toBeVisible()
        await checkPage(page, problems, { noSideScroll: false })
    }
})
