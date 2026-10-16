import { defineStore } from 'pinia'
import apiOnboarding from '@/apis/onboarding/apiOnboarding'
import { apiErrorMessage } from '@/lib/axiosPolicy.js'
import { fileToBase64 } from '@/utils/fileToBase64'
import { i18n } from '@/plugins/i18n'

const INVITE_ONLY = ['enterprise']

export const BANKS = ['Vietcombank', 'VietinBank', 'BIDV', 'Agribank', 'Techcombank', 'MB Bank', 'ACB', 'VPBank', 'Sacombank', 'TPBank', 'HDBank', 'VIB', 'Shinhan Bank', 'Other']
export const NATIONALITIES = ['Philippines', 'Vietnam', 'Other']
export const DOCUMENT_KINDS = ['id_document', 'residence_card', 'food_safety', 'business_registration']
export const STEP_COUNT = 8

const MAX_SIDE = 1600
const DRAFT_KEY = 'sariko_join_draft'
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const MAPS_RE = /^https?:\/\/(maps\.app\.goo\.gl\/|goo\.gl\/maps|maps\.google\.com(\.vn)?\/|(www\.)?google\.com(\.vn)?\/maps)/i

function emptyForm() {
    return {
        first_name: '', last_name: '', date_of_birth: '',
        nationality: 'Philippines', nationality_other: '',
        id_type: 'passport', id_number: '',
        email: '', phone: '', residential_address: '',
        tax_code: '', tax_resident: null,               // 'yes' | 'no' | 'unsure'
        tier: 'tindahan', founding_invited: false,
        store_name: '', store_description: '', pickup_address: '', maps_link: '',
        opening_time: '', closing_time: '',
        bank_name: '', bank_name_other: '', bank_account_number: '', bank_account_holder: '',
    }
}

function squash(text) {
    return (text || '').trim().replace(/\s+/g, ' ')
}

function isVnPhone(phone) {
    let digits = (phone || '').replace(/\D/g, '')
    if (digits.startsWith('84')) digits = digits.slice(2)
    else if (digits.startsWith('0')) digits = digits.slice(1)
    return /^[1-9]\d{8,9}$/.test(digits)
}

function ageOn(dob, today) {
    const born = new Date(dob)
    let age = today.getFullYear() - born.getFullYear()
    if (today.getMonth() < born.getMonth() || (today.getMonth() === born.getMonth() && today.getDate() < born.getDate())) age--
    return age
}

// Downscale to 1600px JPEG before upload (phone photos are 2-5 MB; 4G is slow).
// The backend compresses again; this is only about upload time.
function compressImage(file) {
    return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file)
        const img = new Image()
        img.onload = () => {
            const scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight))
            const canvas = document.createElement('canvas')
            canvas.width = Math.round(img.naturalWidth * scale)
            canvas.height = Math.round(img.naturalHeight * scale)
            const ctx = canvas.getContext('2d')
            ctx.fillStyle = '#fff'
            ctx.fillRect(0, 0, canvas.width, canvas.height)
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
            URL.revokeObjectURL(url)
            canvas.toBlob(
                (blob) => blob ? resolve(new File([blob], 'photo.jpg', { type: 'image/jpeg' })) : reject(new Error('encode')),
                'image/jpeg', 0.85,
            )
        }
        img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('decode')) }
        img.src = url
    })
}

// Images are re-encoded to JPEG; PDFs pass through. Throws an i18n key on a bad file.
async function prepareFile(file, allowPdf, maxBytes) {
    if (file.type === 'application/pdf') {
        if (!allowPdf) throw 'join_page.error_photo_type'
        if (file.size > maxBytes) throw 'join_page.error_file_size'
        return file
    }
    let out
    try {
        out = await compressImage(file)
    } catch {
        throw allowPdf ? 'join_page.error_file_type' : 'join_page.error_photo_type'
    }
    if (out.size > maxBytes) throw 'join_page.error_file_size'
    return out
}

function newKey() {
    return Math.random().toString(36).slice(2, 10)
}

export const useJoinStore = defineStore('joinStore', {
    state() {
        return {
            settings: null,            // GET /onboarding/settings (limits from admin_settings + admin_tier_config)
            settingsFailed: false,
            step: 1,
            touched: {},               // step -> true once Continue was pressed: show errors from then on
            form: emptyForm(),
            menu: [],                  // [{ key, category, name, description, price, unit_label, preorder, preorder_day }]
            photos: {},                // dish key -> { file, url }   (not saved in the draft)
            documents: { id_document: [], residence_card: [], food_safety: [], business_registration: [] },
            agree: { accurate: false, fees: false, data: false, agreement: false },
            signature_name: '',
            turnstileToken: null,
            turnstileWidgetId: null,

            // submit
            submitting: false,
            progress: { done: 0, total: 0 },
            submitError: null,         // translated message
            application: null,         // { id, upload_token, payload } once created
            uploaded: {},              // upload job id -> true
            reference: null,
        }
    },

    getters: {
        tiers(state) {
            return (state.settings?.tiers || []).map(t => ({
                id: t.tier,
                monthlyFee: t.monthly_fee_vnd,
                commission: t.commission_percent,
                maxItems: t.max_items,
                maxCategories: t.max_categories,
                invite: INVITE_ONLY.includes(t.tier),
            }))
        },

        tier(state) {
            return this.tiers.find(t => t.id === state.form.tier) || this.tiers[0]
        },

        maxItems(state) {
            const cap = state.settings.max_dishes
            return Math.min(this.tier.maxItems ?? cap, cap)
        },

        // Params for every join_page message that shows a limit.
        limits(state) {
            const s = state.settings || {}
            return {
                mb: s.max_file_mb,
                maxFiles: s.max_files_per_kind,
                maxPrice: new Intl.NumberFormat('vi-VN').format(s.max_dish_price || 0),
                maxPreorder: s.max_preorder_days,
                minAge: s.min_age,
                days: s.review_days,
                items: this.maxItems,
                categories: this.tier?.maxCategories,
            }
        },

        // Founding offer text: {slots} {months} {fee} {rate}
        founding(state) {
            const f = state.settings?.founding || {}
            return {
                slots: f.slots,
                months: f.free_months,
                fee: new Intl.NumberFormat('vi-VN').format(f.monthly_fee_vnd || 0) + ' ₫',
                rate: f.commission_percent,
            }
        },

        // 20261016 -> "2026-10-16" (same date as the agreement page header)
        agreementLabel(state) {
            const v = String(state.settings?.agreement_version || '')
            return `${v.slice(0, 4)}-${v.slice(4, 6)}-${v.slice(6, 8)}`
        },

        categories(state) {
            const seen = new Map()
            for (const dish of state.menu) {
                const name = squash(dish.category)
                if (name && !seen.has(name.toLowerCase())) seen.set(name.toLowerCase(), name)
            }
            return [...seen.values()]
        },

        fullName(state) {
            return squash(`${state.form.first_name} ${state.form.last_name}`)
        },

        // { field: i18n key } for one step. Empty object = step is valid.
        stepErrors(state) {
            return (step) => {
                const f = state.form
                const s = state.settings
                const e = {}
                const need = (field, value = f[field]) => { if (!squash(value)) e[field] = 'join_page.error_required' }

                if (step === 2) {
                    need('first_name'); need('last_name'); need('id_number'); need('residential_address')
                    if (!f.date_of_birth) e.date_of_birth = 'join_page.error_required'
                    else if (ageOn(f.date_of_birth, new Date()) < s.min_age) e.date_of_birth = 'join_page.error_age'
                    if (f.nationality === 'Other') need('nationality_other')
                    if (!EMAIL_RE.test(f.email.trim())) e.email = 'join_page.error_email'
                    if (!isVnPhone(f.phone)) e.phone = 'join_page.error_phone'
                    if (!f.tax_resident) e.tax_resident = 'join_page.error_required'
                }
                if (step === 4) {
                    need('store_name'); need('pickup_address')
                    if (f.maps_link.trim() && !MAPS_RE.test(f.maps_link.trim())) e.maps_link = 'join_page.error_maps_link'
                    if (f.opening_time && f.closing_time && f.opening_time >= f.closing_time) e.closing_time = 'join_page.error_hours'
                }
                if (step === 5) {
                    if (!state.menu.length) e.menu = 'join_page.error_menu_empty'
                    else if (state.menu.length > this.maxItems) e.menu = 'join_page.error_too_many_items'
                    else if (this.tier.maxCategories !== null && this.categories.length > this.tier.maxCategories) e.menu = 'join_page.error_too_many_categories'
                    const names = new Set()
                    for (const dish of state.menu) {
                        const de = {}
                        if (!squash(dish.category)) de.category = 'join_page.error_required'
                        if (!squash(dish.name)) de.name = 'join_page.error_required'
                        const price = Number(dish.price)
                        if (!Number.isInteger(price) || price <= 0 || price > s.max_dish_price) de.price = 'join_page.error_price'
                        if (dish.preorder && !(dish.preorder_day >= 1 && dish.preorder_day <= s.max_preorder_days)) de.preorder_day = 'join_page.error_preorder_day'
                        const nameKey = `${squash(dish.category).toLowerCase()}|${squash(dish.name).toLowerCase()}`
                        if (squash(dish.name) && names.has(nameKey)) de.name = 'join_page.error_duplicate_dish'
                        names.add(nameKey)
                        if (!state.photos[dish.key]) de.photo = 'join_page.error_photo_required'
                        if (Object.keys(de).length) e[`dish:${dish.key}`] = de
                    }
                }
                if (step === 6) {
                    if (!state.documents.id_document.length) e.id_document = 'join_page.error_id_document'
                }
                if (step === 7) {
                    need('bank_account_holder')
                    if (!f.bank_name) e.bank_name = 'join_page.error_required'
                    else if (f.bank_name === 'Other') need('bank_name_other')
                    if (!/^\d{6,20}$/.test(f.bank_account_number.replace(/\s/g, ''))) e.bank_account_number = 'join_page.error_account_number'
                }
                if (step === 8) {
                    if (!Object.values(state.agree).every(Boolean)) e.agree = 'join_page.error_agree'
                    const sig = squash(state.signature_name).toLowerCase()
                    const first = squash(f.first_name).toLowerCase()
                    const last = squash(f.last_name).toLowerCase()
                    if (sig !== `${first} ${last}` && sig !== `${last} ${first}`) e.signature_name = 'join_page.error_signature'
                }
                return e
            }
        },

        // Shown only after the step's Continue was pressed once.
        visibleErrors() {
            return (step) => this.touched[step] ? this.stepErrors(step) : {}
        },

        dishErrors() {
            return (key) => this.visibleErrors(5)[`dish:${key}`] || {}
        },
    },

    actions: {
        // ── navigation ────────────────────────────────────────────────────

        next() {
            this.touched = { ...this.touched, [this.step]: true }
            if (Object.keys(this.stepErrors(this.step)).length) return false
            this.step = Math.min(this.step + 1, STEP_COUNT)
            return true
        },

        back() {
            this.step = Math.max(this.step - 1, 1)
        },

        async loadSettings() {
            this.settingsFailed = false
            try {
                this.settings = await apiOnboarding.getSettings()
            } catch (e) {
                this.settingsFailed = true
                console.error('joinStore - loadSettings -', e)
            }
        },

        // ── draft (text only; files can't be stored) ───────────────────────

        loadDraft() {
            try {
                const draft = JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null')
                if (!draft) return
                this.form = { ...emptyForm(), ...draft.form }
                this.menu = Array.isArray(draft.menu) ? draft.menu : []
                this.step = draft.step || 1
            } catch (e) {
                console.warn('joinStore - loadDraft -', e)
            }
        },

        saveDraft() {
            try {
                localStorage.setItem(DRAFT_KEY, JSON.stringify({ form: this.form, menu: this.menu, step: this.step }))
            } catch (e) {
                console.warn('joinStore - saveDraft -', e)
            }
        },

        clearDraft() {
            try { localStorage.removeItem(DRAFT_KEY) } catch { /* private mode */ }
        },

        // ── menu ──────────────────────────────────────────────────────────

        addDish() {
            if (this.menu.length >= this.maxItems) return
            const last = this.menu[this.menu.length - 1]
            this.menu.push({
                key: newKey(), category: last?.category || '', name: '', description: '',
                price: null, unit_label: '', preorder: false, preorder_day: 1,
            })
        },

        removeDish(key) {
            this.menu = this.menu.filter(d => d.key !== key)
            if (this.photos[key]) URL.revokeObjectURL(this.photos[key].url)
            const { [key]: _removed, ...rest } = this.photos
            this.photos = rest
        },

        async setPhoto(key, file) {
            const prepared = await prepareFile(file, false, this.settings.max_file_mb * 1024 * 1024)
            if (this.photos[key]) URL.revokeObjectURL(this.photos[key].url)
            this.photos = { ...this.photos, [key]: { file: prepared, url: URL.createObjectURL(prepared) } }
            delete this.uploaded[`dish:${key}`]
        },

        // ── documents ─────────────────────────────────────────────────────

        async addDocument(kind, file) {
            if (this.documents[kind].length >= this.settings.max_files_per_kind) throw 'join_page.error_too_many_files'
            const prepared = await prepareFile(file, true, this.settings.max_file_mb * 1024 * 1024)
            this.documents[kind].push({ file: prepared, name: file.name })
            this.application = null    // the backend can't drop a document: start a fresh application
        },

        removeDocument(kind, index) {
            this.documents[kind].splice(index, 1)
            this.application = null
        },

        // ── submit: create -> upload each file -> submit ───────────────────

        payload() {
            const f = this.form
            return {
                first_name: squash(f.first_name), last_name: squash(f.last_name),
                date_of_birth: f.date_of_birth,
                nationality: f.nationality === 'Other' ? squash(f.nationality_other) : f.nationality,
                id_type: f.id_type, id_number: squash(f.id_number),
                email: f.email.trim(), phone: f.phone.trim(),
                residential_address: squash(f.residential_address),
                tax_code: squash(f.tax_code) || null,
                tax_resident: { yes: true, no: false }[f.tax_resident] ?? null,
                store_name: squash(f.store_name), store_description: f.store_description.trim() || null,
                pickup_address: squash(f.pickup_address), maps_link: f.maps_link.trim() || null,
                opening_time: f.opening_time || null, closing_time: f.closing_time || null,
                menu: this.menu.map(d => ({
                    key: d.key, category: squash(d.category), name: squash(d.name),
                    description: squash(d.description) || null, price: Number(d.price),
                    unit_label: squash(d.unit_label) || null,
                    preorder_day: d.preorder ? Number(d.preorder_day) : 0,
                })),
                tier: f.tier, founding_invited: f.founding_invited,
                bank_name: f.bank_name === 'Other' ? squash(f.bank_name_other) : f.bank_name,
                bank_account_number: f.bank_account_number.replace(/\s/g, ''),
                bank_account_holder: squash(f.bank_account_holder),
                agreed: true, agreement_version: this.settings.agreement_version,
                signature_name: squash(this.signature_name),
            }
        },

        uploadJobs() {
            const jobs = []
            for (const kind of DOCUMENT_KINDS) {
                this.documents[kind].forEach((doc, i) => jobs.push({ id: `${kind}:${i}`, kind, file: doc.file }))
            }
            for (const dish of this.menu) {
                jobs.push({ id: `dish:${dish.key}`, kind: 'dish_photo', item_key: dish.key, file: this.photos[dish.key].file })
            }
            return jobs
        },

        resetCaptcha() {
            this.turnstileToken = null
            try {
                if (window.turnstile && this.turnstileWidgetId !== null) window.turnstile.reset(this.turnstileWidgetId)
            } catch { /* widget gone */ }
        },

        async submit() {
            this.touched = { ...this.touched, 8: true }
            for (let step = 2; step <= STEP_COUNT; step++) {
                if (Object.keys(this.stepErrors(step)).length) {
                    this.touched = { ...this.touched, [step]: true }
                    if (step !== 8) this.step = step
                    return
                }
            }
            this.submitting = true
            this.submitError = null
            try {
                // Edited after the last attempt (or never created): new application, needs a fresh captcha.
                const payload = this.payload()
                if (!this.application || JSON.stringify(payload) !== this.application.payload) {
                    if (!this.turnstileToken) {
                        this.submitError = i18n.global.t('join_page.error_captcha_wait')
                        return
                    }
                    const token = this.turnstileToken
                    this.resetCaptcha()   // tokens are single-use
                    const res = await apiOnboarding.createApplication({ ...payload, turnstile_token: token })
                    this.application = { id: res.id, upload_token: res.upload_token, payload: JSON.stringify(payload) }
                    this.uploaded = {}
                }

                const jobs = this.uploadJobs()
                this.progress = { done: jobs.filter(j => this.uploaded[j.id]).length, total: jobs.length }
                for (const job of jobs) {
                    if (this.uploaded[job.id]) continue
                    await apiOnboarding.uploadFile(this.application.id, this.application.upload_token, {
                        kind: job.kind,
                        item_key: job.item_key || null,
                        file_base64: await fileToBase64(job.file),
                        content_type: job.file.type,
                    })
                    this.uploaded[job.id] = true
                    this.progress.done++
                }

                const res = await apiOnboarding.submitApplication(this.application.id, this.application.upload_token)
                this.reference = res.reference
                this.clearDraft()
            } catch (e) {
                const data = e?.response?.data
                const code = data?.detail?.code
                if (code === 'application_not_found') {
                    // Over 3 hours since create (or already submitted): start over with a new captcha.
                    this.application = null
                    this.submitError = i18n.global.t('join_page.error_expired')
                } else {
                    this.submitError = e?.response ? apiErrorMessage(data) : i18n.global.t('join_page.error_network')
                }
                // Agreement changed since the page loaded: pick up the new version (the iframe shows the new text).
                if (code === 'agreement_outdated') await this.loadSettings()
                console.error('joinStore - submit -', e)
            } finally {
                this.submitting = false
            }
        },
    },
})
