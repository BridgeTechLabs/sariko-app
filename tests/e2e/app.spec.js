// App smoke on DEV at 390 (docs/dev/e2e-smoke E2E-1..7). Each test makes its own "TEST e2e" data and removes it.
import { test, expect } from '@playwright/test'
import { api, checkPage, guest, signIn, t, watch } from './lib.js'

const SELLER_SLUG = process.env.E2E_SELLER_SLUG || 'rosa-home-kitchen'   // the DEV_SELLER store
const STAMP = `TEST e2e ${new Date().toISOString().slice(0, 16).replace('T', ' ')}`
const PRICE = /[1-9]\d{0,2}(\.\d{3})* ₫/

// The dishes (objects with a price) anywhere in a menu answer.
function menuItems(menu, found = []) {
    if (Array.isArray(menu)) menu.forEach((x) => menuItems(x, found))
    else if (menu && typeof menu === 'object') 'price' in menu ? found.push(menu) : Object.values(menu).forEach((x) => menuItems(x, found))
    return found
}

// A dish of the DEV seller that can go in a cart: no price options, on sale, same-day or pre-order.
async function dish(page, preorder) {
    const { body: { seller } } = await api(page, 'GET', `/sellers/${SELLER_SLUG}`)
    const { body } = await api(page, 'GET', `/sellers/${SELLER_SLUG}/menu`)
    const item = menuItems(body.menus).find((i) => i.is_available !== false && !(i.food_item_variants || []).length && (i.preorder_day > 0) === preorder)
    expect(item, `a ${preorder ? 'pre-order' : 'same-day'} dish at ${SELLER_SLUG}`).toBeTruthy()
    return { seller_id: seller.id, food_item_id: item.id }
}

async function fillCart(page, preorder = false) {
    await api(page, 'DELETE', '/cart/clear')   // 404 when there is no cart
    const added = await api(page, 'POST', '/cart/add', { ...(await dish(page, preorder)), quantity: 1 })
    expect(added.status, 'add to cart').toBe(200)
}

// A non-default address of this run, so the picker has something to switch to.
async function testAddress(page) {
    const { body } = await api(page, 'POST', '/user_addresses', {
        label: STAMP, receiver_name: `${STAMP} receiver`, phone_number: '0901234567', note: STAMP,
        address: '135 Nam Ky Khoi Nghia, Ben Thanh, District 1, Ho Chi Minh City', lat: 10.7769, lon: 106.6953,
    })
    return body.address
}

async function defaultAddressId(page) {
    return (await api(page, 'GET', '/user_addresses')).body.addresses.find((a) => a.is_default)?.id
}

// Cart "Deliver to" card: its pen opens the address sheet; pick this run's address.
async function pickAddress(page, address) {
    await page.goto('/cart')
    const card = page.getByText(new RegExp(t('cart_page.section_delivery_address.title', { name: '' }).trim(), 'i'))
    await card.locator('xpath=ancestor::*[.//button][1]').getByRole('button').first().click()
    const sheet = page.getByRole('dialog')
    await expect(sheet.getByText(t('cart_page.section_delivery_address.sheet_title'))).toBeVisible()
    await sheet.getByRole('button', { name: new RegExp(address.label) }).click()
    await expect(sheet).toBeHidden()
    await expect(page.getByText(address.receiver_name)).toBeVisible()
}

async function deliveryFee(page) {
    return page.getByText(t('cart_page.section_total_amount.title_estimated_delivery_fee')).locator('xpath=..').innerText()
}

test('E2E-1 buyer home shows dishes', async ({ page }) => {
    const problems = watch(page)
    await signIn(page, 'BUYER')
    await page.goto('/')
    await expect(page.getByText(t('home_page.section_featured_dishes.title'))).toBeVisible()
    await expect(page.getByText(PRICE).first()).toBeVisible()
    await checkPage(page, problems)
})

test('E2E-2 cart picks another address for this order only', async ({ page }) => {
    const problems = watch(page)
    await signIn(page, 'BUYER')
    const before = await defaultAddressId(page)
    const address = await testAddress(page)
    try {
        await fillCart(page)
        await pickAddress(page, address)
        await expect.poll(() => deliveryFee(page), { message: 'delivery fee re-quoted' }).toMatch(PRICE)
        expect(await defaultAddressId(page), 'default address unchanged').toBe(before)
        await checkPage(page, problems)
    } finally {
        await api(page, 'DELETE', `/user_addresses/${address.id}`)
        await api(page, 'DELETE', '/cart/clear')
    }
})

test('E2E-3 place order goes to the VNPay sandbox', async ({ page }) => {
    const started = new Date().toISOString()
    await signIn(page, 'BUYER')
    const address = await testAddress(page)
    let order
    try {
        await fillCart(page)
        await pickAddress(page, address)
        await expect.poll(() => deliveryFee(page)).toMatch(PRICE)
        await page.getByPlaceholder(t('cart_page.note_placeholder')).fill(STAMP)
        await page.getByRole('checkbox').check()
        const app = new URL(page.url()).host
        await page.getByRole('button', { name: new RegExp(t('cart_page.section_total_amount.button_label_checkout')) }).click()
        await page.waitForURL((u) => u.host !== app, { timeout: 30_000 })
        // Nothing is clicked on the payment page: real money only exists on PROD's VNPay
        expect(new URL(page.url()).host, 'VNPay sandbox, never the live gateway').toMatch(/sandbox\.vnpayment\.vn$/)
        order = (await api(page, 'GET', '/orders')).body.orders.find((o) => o.created_at > started)
        expect(order, 'the order of this run').toBeTruthy()
        const detail = (await api(page, 'GET', `/orders/${order.id}`)).body.order
        expect(detail.note).toBe(STAMP)
        expect(detail.payment_status).not.toBe('paid')
    } finally {
        if (order) await api(page, 'PATCH', `/dev/orders/${order.id}/force-status`, { status: 'cancelled' })
        await api(page, 'DELETE', `/user_addresses/${address.id}`)
        await api(page, 'DELETE', '/cart/clear')
    }
})

test('E2E-4 pre-order date picker moves to next month', async ({ page }) => {
    const problems = watch(page)
    await signIn(page, 'BUYER')
    try {
        await fillCart(page, true)
        await page.goto('/cart')
        const date = page.getByPlaceholder(t('cart_page.preorder.placeholder_date'))
        await date.locator('xpath=ancestor::label[1]').locator('svg').last().click()
        const month = page.getByRole('button', { name: /^(January|February|March|April|May|June|July|August|September|October|November|December)$/ })
        const shown = await month.innerText()
        await page.getByRole('button', { name: /next month/i }).click()
        await expect.poll(() => month.allInnerTexts(), { message: 'month changed' }).not.toContain(shown)
        await page.getByRole('button', { name: /^\d{1,2}$/ }).filter({ hasNot: page.locator('[disabled]') }).first().click()
        await expect(date).not.toHaveValue('')
        await checkPage(page, problems)
    } finally {
        await api(page, 'DELETE', '/cart/clear')
    }
})

test('E2E-5 seller accepts a paid order and sees its receiver', async ({ page, browser }) => {
    await signIn(page, 'BUYER')
    const address = await testAddress(page)
    let order
    try {
        await fillCart(page)
        const where = { delivery_address: address.address, delivery_lat: address.lat, delivery_lon: address.lon }
        const quote = await api(page, 'POST', '/deliveries/quotation', { seller_id: (await dish(page, false)).seller_id, ...where })
        const made = await api(page, 'POST', '/orders', {
            delivery_method: 'delivery', ...where, delivery_fee: quote.body.total_fee, quotation_id: quote.body.quotation_id,
            note: STAMP, receiver_name: address.receiver_name, receiver_phone: address.phone_number,
        })
        expect(made.status, 'order created').toBe(200)
        order = made.body.order
        const paid = await api(page, 'PATCH', `/dev/orders/${order.id}/force-pay`)
        expect(paid.status, 'router /dev is mounted (DEV / local only); without it this test cannot pay an order').toBe(200)

        const seller = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage()
        const problems = watch(seller)
        await signIn(seller, 'SELLER')
        await seller.goto(`/seller/orders/${order.id}`)
        await expect(seller.getByText(address.receiver_name)).toBeVisible()
        await seller.getByRole('button', { name: t('seller_order_detail.action_accept_order') }).click()
        await expect.poll(async () => (await api(seller, 'GET', `/sellers/me/orders/${order.id}`)).body.order?.status).toBe('confirmed')
        await checkPage(seller, problems)
    } finally {
        if (order) await api(page, 'PATCH', `/dev/orders/${order.id}/force-status`, { status: 'cancelled' })
        await api(page, 'DELETE', `/user_addresses/${address.id}`)
        await api(page, 'DELETE', '/cart/clear')
    }
})

test('E2E-6 seller opens a dish to edit and closes without saving', async ({ page }) => {
    const problems = watch(page)
    await signIn(page, 'SELLER')
    const [first] = menuItems((await api(page, 'GET', '/sellers/me/menu')).body.menu)
    await page.goto('/seller/menu')
    // the dish row's first button is its pencil
    await page.getByText(first.name, { exact: true }).first().locator('xpath=ancestor::*[.//button][1]').getByRole('button').first().click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.getByRole('combobox').first()).toBeVisible()
    await checkPage(page, problems)
    await page.keyboard.press('Escape')
})

test('E2E-7 join wizard reaches step 2 (never submitted)', async ({ page }) => {
    const problems = watch(page)
    await guest(page)
    await page.goto('/join')
    await expect(page.getByText(t('join_page.step_welcome'))).toBeVisible()
    await page.getByRole('button', { name: t('join_page.button_continue') }).click()
    await expect(page.getByLabel(t('join_page.label_full_name'))).toBeVisible()
    await checkPage(page, problems)
})
