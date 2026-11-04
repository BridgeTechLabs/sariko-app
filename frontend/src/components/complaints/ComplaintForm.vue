<script>
import { Camera, X, CheckCircle2 } from 'lucide-vue-next';
import { useComplaintStore } from '@/stores/complaint/complaintStore';
import { orderCode } from '@/utils/orderCode';

// T35: file a complaint about one order (?order=<id>&as=buyer|seller). Types, photo count and length
// come from GET /complaints/config; the backend checks everything again.
export default {
    components: { Camera, X, CheckCircle2 },

    computed: {
        store() {
            return useComplaintStore()
        },
        orderId() {
            return this.$route.query.order
        },
        role() {
            return this.$route.query.as === 'seller' ? 'seller' : 'buyer'
        },
        config() {
            return this.store.config
        },
        categories() {
            return this.config?.categories?.[this.role] || []
        },
        previews() {
            return this.store.files.map(f => URL.createObjectURL(f))
        },
        canSubmit() {
            return !!this.store.category && !!this.store.description.trim()
                && this.store.description.length <= this.config.max_length && !this.store.submitting
        },
        errorText() {
            const e = this.store.error
            if (!e) return ''
            const key = `complaints.errors.${e.code}`
            return this.$te(key) ? this.$t(key, e.params) : this.$t('complaints.errors.generic')
        },
        orderLabel() {
            return this.$t('complaints.order_label', { code: orderCode(this.orderId) })
        },
    },

    methods: {
        pickFiles(event) {
            const room = this.config.max_images - this.store.files.length
            const tooBig = [...event.target.files].filter(f => f.size > this.config.max_file_mb * 1024 * 1024)
            if (tooBig.length) {
                this.$q.notify({ type: 'warning', message: this.$t('complaints.errors.file_too_large', { mb: this.config.max_file_mb }), position: 'top' })
            }
            const ok = [...event.target.files].filter(f => !tooBig.includes(f))
            this.store.files = [...this.store.files, ...ok.slice(0, room)]
            event.target.value = ''
        },
        removeFile(i) {
            this.store.files = this.store.files.filter((_, idx) => idx !== i)
        },
        backToOrder() {
            this.$router.replace(this.role === 'seller' ? `/seller/orders/${this.orderId}` : `/orders/${this.orderId}`)
        },
    },
}
</script>

<template>
    <div v-if="!config" class="form">
        <q-skeleton type="rect" height="90px" style="border-radius:12px;" animation="pulse" />
        <q-skeleton type="rect" height="140px" style="border-radius:12px;" animation="pulse" />
    </div>

    <!-- Sent: the tracking code -->
    <div v-else-if="store.created" class="sent">
        <CheckCircle2 :size="40" class="sent-icon" />
        <div class="sent-title">{{ $t('complaints.sent_title') }}</div>
        <div class="sent-code">{{ store.created.code }}</div>
        <div class="sent-body">{{ $t('complaints.sent_body', { ack: config.ack_hours, days: config.resolve_working_days }) }}</div>
        <div v-if="store.created.imagesFailed" class="sent-warn">
            {{ $t('complaints.images_failed', { n: store.created.imagesFailed }) }}
        </div>
        <q-btn class="btn-primary" no-caps dense @click="$router.replace(`/complaints/${store.created.id}`)">
            {{ $t('complaints.btn_view') }}
        </q-btn>
        <q-btn class="btn-secondary" flat no-caps dense @click="backToOrder">{{ $t('complaints.btn_back_order') }}</q-btn>
    </div>

    <div v-else class="form">
        <div class="order-label">{{ orderLabel }}</div>

        <div class="field">
            <div class="field-label">{{ $t('complaints.field_category') }}</div>
            <div class="options">
                <button v-for="c in categories" :key="c" type="button" class="option"
                        :class="{ active: store.category === c }" @click="store.category = c">
                    {{ $t(`complaints.category.${c}`) }}
                </button>
            </div>
        </div>

        <div class="field">
            <div class="field-label">{{ $t('complaints.field_description') }}</div>
            <q-input v-model="store.description" type="textarea" outlined dark autogrow
                     :maxlength="config.max_length" :placeholder="$t('complaints.description_hint')" class="desc" />
            <div class="counter">{{ store.description.length }}/{{ config.max_length }}</div>
        </div>

        <div class="field">
            <div class="field-label">{{ $t('complaints.field_photos', { max: config.max_images }) }}</div>
            <div class="photos">
                <div v-for="(src, i) in previews" :key="src" class="photo">
                    <img :src="src" alt="" />
                    <button type="button" class="photo-remove" :aria-label="$t('complaints.remove_photo')" @click="removeFile(i)">
                        <X :size="14" />
                    </button>
                </div>
                <label v-if="store.files.length < config.max_images" class="photo-add">
                    <Camera :size="20" />
                    <span>{{ $t('complaints.add_photo') }}</span>
                    <input type="file" accept="image/jpeg,image/png" multiple hidden @change="pickFiles" />
                </label>
            </div>
        </div>

        <div class="window-note">{{ $t('complaints.window_note', { hours: config.window_hours }) }}</div>
        <div v-if="errorText" class="error">{{ errorText }}</div>

        <q-btn class="btn-primary" no-caps dense :disable="!canSubmit" :loading="store.submitting" @click="store.submit(orderId)">
            {{ $t('complaints.submit') }}
        </q-btn>
    </div>
</template>

<style scoped>
.form, .sent {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.order-label {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-secondary);
}

.field {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.field-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
}

.options {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.option {
    padding: 8px 12px;
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: transparent;
    color: var(--text-secondary);
    font-size: 13px;
    cursor: pointer;
}

.option.active {
    border-color: var(--color-accent);
    color: var(--color-accent);
    background: rgba(255, 255, 255, 0.05);
}

.counter {
    align-self: flex-end;
    font-size: 11px;
    color: var(--text-muted);
}

.photos {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}

.photo, .photo-add {
    width: 84px;
    height: 84px;
    border-radius: 12px;
    position: relative;
    overflow: hidden;
}

.photo img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.photo-remove {
    position: absolute;
    top: 4px;
    right: 4px;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: none;
    background: rgba(0, 0, 0, 0.6);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.photo-add {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    border: 1px dashed rgba(255, 255, 255, 0.25);
    color: var(--text-secondary);
    font-size: 11px;
    cursor: pointer;
}

.window-note {
    font-size: 12px;
    color: var(--text-muted);
}

.error {
    font-size: 13px;
    color: #ef4444;
}

.btn-primary {
    width: 100%;
    background-color: var(--color-accent);
    color: #121b2f;
    padding: 14px 0;
    border-radius: 2rem;
    font-weight: 700;
    font-size: 16px;
}

.btn-secondary {
    width: 100%;
    color: var(--text-secondary);
    padding: 10px 0;
}

.sent {
    align-items: center;
    text-align: center;
    padding-top: 24px;
}

.sent-icon {
    color: var(--color-success);
}

.sent-title {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
}

.sent-code {
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 1px;
    color: var(--color-accent);
}

.sent-body {
    font-size: 13px;
    color: var(--text-secondary);
}

.sent-warn {
    font-size: 13px;
    color: var(--color-warning);
}
</style>
