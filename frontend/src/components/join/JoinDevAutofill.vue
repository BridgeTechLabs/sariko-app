<script>
import { useJoinStore, BANKS, DOCUMENT_KINDS, STEP_COUNT } from '@/stores/join/joinStore'

// DEV ONLY (loaded only when VITE_DEV_PANEL=true, like HackerPanel): fills the whole
// /join form with sample data so a reviewer can click through to Review.
// Writes the store directly; no API calls; Turnstile is still solved by hand.

const DISHES = [
    { category: 'Ulam', name: 'Chicken Adobo', description: 'Chicken braised in soy and vinegar', price: 85000, unit_label: 'box', preorder: false },
    { category: 'Ulam', name: 'Pork Sinigang', description: 'Sour tamarind soup', price: 120000, unit_label: 'bowl', preorder: false },
    { category: 'Dessert', name: 'Leche Flan', description: 'Steamed caramel custard', price: 65000, unit_label: 'tub', preorder: true },
]

// Fake JPEG drawn on a canvas (a few dozen KB), so no image files go into the repo.
function fakeJpeg(label, color) {
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 480
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = color
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.fillStyle = '#fff'
    ctx.textAlign = 'center'
    ctx.font = 'bold 72px sans-serif'
    ctx.fillText('TEST', 320, 220)
    ctx.font = '32px sans-serif'
    ctx.fillText(label, 320, 290)
    return new Promise((resolve) => canvas.toBlob(
        (blob) => resolve(new File([blob], `${label}.jpg`, { type: 'image/jpeg' })),
        'image/jpeg', 0.7,
    ))
}

function isoDate(d) {
    return d.toISOString().slice(0, 10)
}

export default {
    data() {
        return { busy: false }
    },

    computed: {
        store() {
            return useJoinStore()
        },
    },

    methods: {
        hasData() {
            const s = this.store
            return !!(s.form.first_name || s.form.store_name || s.menu.some(d => d.name) || DOCUMENT_KINDS.some(k => s.documents[k].length))
        },

        async fill() {
            if (this.hasData() && !window.confirm('Overwrite the form with test data?')) return
            this.busy = true
            try {
                const s = this.store
                const settings = s.settings
                const now = new Date()
                const hhmm = now.toTimeString().slice(0, 5)
                const dob = new Date(now)
                dob.setFullYear(now.getFullYear() - settings.min_age - 12)

                Object.assign(s.form, {
                    first_name: 'Maria', last_name: 'Santos', date_of_birth: isoDate(dob),
                    nationality: 'Philippines', nationality_other: '',
                    id_type: 'passport', id_number: `P${String(now.getTime()).slice(-7)}`,
                    email: `test+${now.getTime()}@example.com`, phone: '0901234567',
                    residential_address: '12 Nguyen Hue, Ben Nghe, District 1, Ho Chi Minh City',
                    tax_code: '', tax_resident: 'yes',
                    tier: s.tiers.some(t => t.id === 'tindahan') ? 'tindahan' : s.tiers[0].id,
                    founding_invited: false,
                    store_name: `TEST autofill ${hhmm}`,
                    store_description: 'Test store filled by the DEV autofill button.',
                    pickup_address: '12 Nguyen Hue, Ben Nghe, District 1, Ho Chi Minh City',
                    maps_link: 'https://maps.app.goo.gl/test',
                    opening_time: '09:00', closing_time: '20:00',
                    bank_name: BANKS[0], bank_name_other: '',
                    bank_account_number: '0123456789',
                })
                s.form.bank_account_holder = s.fullName.toUpperCase()

                // Menu within the plan's limits (from /onboarding/settings).
                for (const d of [...s.menu]) s.removeDish(d.key)
                const allowed = [...new Set(DISHES.map(d => d.category))].slice(0, s.tier.maxCategories ?? undefined)
                const dishes = DISHES.filter(d => allowed.includes(d.category)).slice(0, s.maxItems)
                for (const d of dishes) {
                    s.addDish()
                    Object.assign(s.menu[s.menu.length - 1], {
                        ...d,
                        price: Math.min(d.price, settings.max_dish_price),
                        preorder_day: Math.min(1, settings.max_preorder_days),
                    })
                }
                for (const [i, d] of s.menu.entries()) {
                    await s.setPhoto(d.key, await fakeJpeg(d.name, ['#c0392b', '#2471a3', '#7d3c98'][i % 3]))
                }

                for (const kind of DOCUMENT_KINDS) s.documents[kind] = []
                await s.addDocument('id_document', await fakeJpeg('Passport', '#1e8449'))

                s.agree = { accurate: true, fees: true, data: true, agreement: true }
                s.signature_name = s.fullName

                // Same checks as when a user presses Continue on every step.
                const touched = {}
                for (let step = 2; step <= STEP_COUNT; step++) touched[step] = true
                s.touched = touched
                const bad = []
                for (let step = 2; step <= STEP_COUNT; step++) {
                    if (Object.keys(s.stepErrors(step)).length) bad.push(step)
                }
                this.$q.notify({
                    type: bad.length ? 'warning' : 'positive',
                    message: bad.length ? `Autofill: errors on step ${bad.join(', ')}` : 'Autofill done: press Continue to Review, then solve Turnstile',
                    position: 'bottom',
                })
            } catch (e) {
                console.error('JoinDevAutofill -', e)
                this.$q.notify({ type: 'negative', message: `Autofill failed: ${e}`, position: 'bottom' })
            } finally {
                this.busy = false
            }
        },
    },
}
</script>

<template>
    <button type="button" class="dev-autofill" :disabled="busy" @click="fill">
        {{ busy ? 'DEV · filling…' : 'DEV · Autofill' }}
    </button>
</template>

<style scoped>
.dev-autofill {
    /* Narrow (wraps to 2 lines) so it sits in the left gutter: the vertical
       stepper rail on phones, the page margin on desktop, not over form text. */
    position: fixed;
    left: 4px;
    bottom: 12px;
    z-index: 5000; /* above the page, below Quasar dialogs (6000), e.g. the language sheet */
    width: 52px;
    padding: 4px 2px;
    border: 2px dashed #fff;
    border-radius: 8px;
    background: #d10fd1;
    color: #fff;
    font: 600 9px/1.3 monospace;
    text-align: center;
    word-break: break-word;
    cursor: pointer;
    opacity: 0.85;
}

.dev-autofill:disabled {
    opacity: 0.5;
}
</style>
