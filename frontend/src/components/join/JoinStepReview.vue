<script>
import { Pencil } from 'lucide-vue-next'
import JoinTurnstile from '@/components/join/JoinTurnstile.vue'
import { useJoinStore, DOCUMENT_KINDS } from '@/stores/join/joinStore'

const AGREEMENT_URL = '/docs/sariko_seller_agreement.html'

export default {
    components: { Pencil, JoinTurnstile },

    data() {
        return { agreementUrl: AGREEMENT_URL, kinds: DOCUMENT_KINDS }
    },

    computed: {
        store() {
            return useJoinStore()
        },
        form() {
            return this.store.form
        },
        payload() {
            return this.store.payload()
        },
        errors() {
            return this.store.visibleErrors(8)
        },
        summary() {
            const p = this.payload
            const t = (k) => this.$t(`join_page.${k}`)
            const resident = { true: t('resident_yes'), false: t('resident_no') }[p.tax_resident] ?? t('resident_unsure')
            return [
                { step: 2, title: t('step_about'), rows: [
                    [t('label_full_name'), `${p.first_name} ${p.last_name}`],
                    [t('label_date_of_birth'), p.date_of_birth],
                    [t('label_nationality'), p.nationality],
                    [t(`id_type_${p.id_type}`), p.id_number],
                    [t('label_id_expiry'), p.id_expiry_date],
                    [t('label_email'), p.email],
                    [t('label_phone'), p.phone],
                    [t('label_residential_address'), p.residential_address],
                    [t('label_tax_code'), p.tax_code || '—'],
                    [t('label_tax_resident'), resident],
                ] },
                { step: 3, title: t('step_plan'), rows: [
                    [t('step_plan'), t(`tier_${p.tier}`) + (p.founding_invited ? ` · ${t('plan_founding_short')}` : '')],
                ] },
                { step: 4, title: t('step_store'), rows: [
                    [t('label_store_name'), p.store_name],
                    [t('label_pickup_address'), p.pickup_address],
                    [t('label_maps_link'), p.maps_link || '—'],
                    [t('label_hours'), p.opening_time && p.closing_time ? `${p.opening_time} – ${p.closing_time}` : '—'],
                ] },
                { step: 7, title: t('step_payout'), rows: [
                    [t('label_bank_name'), p.bank_name],
                    [t('label_bank_account_number'), p.bank_account_number],
                    [t('label_bank_account_holder'), p.bank_account_holder],
                ] },
            ]
        },
        checks() {
            return [
                { key: 'accurate', label: this.$t('join_page.agree_accurate') },
                { key: 'fees', label: this.$t('join_page.agree_fees') },
                { key: 'data', label: this.$t('join_page.agree_data') },
                { key: 'agreement', label: this.$t('join_page.agree_agreement', { version: this.store.agreementLabel }) },
            ]
        },
    },

    methods: {
        vnd(amount) {
            return new Intl.NumberFormat('vi-VN').format(amount) + ' ₫'
        },
        err(field) {
            return this.errors[field] ? this.$t(this.errors[field], this.store.limits) : ''
        },
        goTo(step) {
            if (!this.store.submitting) this.store.step = step
        },
    },
}
</script>

<template>
    <div class="join-step">
        <div class="join-hint">{{ $t('join_page.review_hint') }}</div>

        <div v-for="s in summary" :key="s.step" class="join-card">
            <div class="card-head">
                <div class="join-label">{{ s.title }}</div>
                <q-btn flat dense no-caps size="sm" class="btn-edit" @click="goTo(s.step)">
                    <Pencil :size="13" />&nbsp;{{ $t('join_page.button_edit') }}
                </q-btn>
            </div>
            <div v-for="[label, value] in s.rows" :key="label" class="row-kv">
                <span class="k">{{ label }}</span>
                <span class="v">{{ value }}</span>
            </div>
        </div>

        <div class="join-card">
            <div class="card-head">
                <div class="join-label">{{ $t('join_page.step_menu') }} · {{ store.menu.length }}</div>
                <q-btn flat dense no-caps size="sm" class="btn-edit" @click="goTo(5)">
                    <Pencil :size="13" />&nbsp;{{ $t('join_page.button_edit') }}
                </q-btn>
            </div>
            <div class="dish-grid">
                <div v-for="dish in payload.menu" :key="dish.key" class="dish">
                    <img v-if="store.photos[dish.key]" :src="store.photos[dish.key].url" alt="" />
                    <div class="dish-name">{{ dish.name }}</div>
                    <div class="dish-meta">{{ dish.category }} · {{ vnd(dish.price) }}</div>
                </div>
            </div>
        </div>

        <div class="join-card">
            <div class="card-head">
                <div class="join-label">{{ $t('join_page.step_documents') }}</div>
                <q-btn flat dense no-caps size="sm" class="btn-edit" @click="goTo(6)">
                    <Pencil :size="13" />&nbsp;{{ $t('join_page.button_edit') }}
                </q-btn>
            </div>
            <div v-for="kind in kinds" :key="kind" class="row-kv">
                <span class="k">{{ $t(`join_page.doc_${kind}`) }}</span>
                <span class="v">{{ store.documents[kind].length }}</span>
            </div>
        </div>

        <div class="join-section-title">{{ $t('join_page.agreement_title') }}</div>
        <iframe :src="agreementUrl" class="agreement" :title="$t('join_page.agreement_title')" />
        <a :href="agreementUrl" target="_blank" rel="noopener" class="join-link">{{ $t('join_page.agreement_open') }}</a>

        <div class="checks">
            <q-checkbox v-for="c in checks" :key="c.key" v-model="store.agree[c.key]" dark dense color="amber" :label="c.label" class="check" />
            <div v-if="err('agree')" class="join-error">{{ err('agree') }}</div>
        </div>

        <q-input
            v-model="store.signature_name"
            dark outlined dense color="amber"
            :label="$t('join_page.label_signature')"
            :hint="$t('join_page.hint_signature', { name: store.fullName })"
            :error="!!err('signature_name')"
            :error-message="err('signature_name')"
            maxlength="300"
        />

        <JoinTurnstile />

        <div v-if="store.submitting && store.progress.total" class="progress">
            {{ $t('join_page.uploading', { done: store.progress.done, total: store.progress.total }) }}
            <q-linear-progress :value="store.progress.done / store.progress.total" color="amber" track-color="grey-8" rounded />
        </div>
        <div v-if="store.submitError" class="submit-error">{{ store.submitError }}</div>

        <q-btn
            unelevated no-caps
            class="btn-submit"
            :loading="store.submitting"
            :disable="store.submitting"
            :label="store.application ? $t('join_page.button_retry') : $t('join_page.button_submit')"
            @click="store.submit()"
        />
    </div>
</template>

<style lang="scss" scoped>
.card-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
}

.btn-edit {
    color: #f5a623;
}

.row-kv {
    display: flex;
    gap: 12px;
    font-size: 13px;
    padding: 3px 0;
}

.k {
    flex: 0 0 40%;
    color: rgba(255, 255, 255, 0.6);
}

.v {
    flex: 1;
    word-break: break-word;
}

.dish-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: 10px;
}

.dish img {
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
    border-radius: 10px;
    display: block;
}

.dish-name {
    font-size: 12px;
    font-weight: 600;
    margin-top: 4px;
}

.dish-meta {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.6);
}

/* tall enough to read on a phone (60% of the screen), scrolls inside; never shorter than before */
.agreement {
    display: block;
    width: 100%;
    height: 60vh;
    min-height: 360px;
    border: 1px solid rgba(245, 166, 35, 0.3);
    border-radius: 12px;
    background: #fff;
}

/* phones: the vertical stepper indents every step 60px; the agreement takes that space back to be readable */
@media (max-width: 599px) {
    .agreement {
        width: calc(100% + 60px);
        margin-left: -60px;
    }
}

.checks {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.check {
    align-items: flex-start;
    font-size: 13px;
    line-height: 1.45;
}

.progress {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 13px;
}

.submit-error {
    font-size: 13px;
    color: #ef4444;
    background: rgba(239, 68, 68, 0.1);
    border-radius: 10px;
    padding: 10px 12px;
}

.btn-submit {
    padding: 12px;
    background: #f5a623;
    color: #121b2f;
    font-weight: 700;
    font-size: 15px;
    border-radius: 12px;
}
</style>
