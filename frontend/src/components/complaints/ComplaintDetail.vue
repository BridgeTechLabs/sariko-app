<script>
import ComplaintStatusChip from '@/components/complaints/ComplaintStatusChip.vue';
import { useComplaintStore } from '@/stores/complaint/complaintStore';
import { orderCode } from '@/utils/orderCode';
import { formatVnTime } from '@/utils/vnTime';

// T35: one complaint as the sender (or the seller of the order) sees it: never the admin's note.
export default {
    components: { ComplaintStatusChip },

    computed: {
        store() {
            return useComplaintStore()
        },
        c() {
            return this.store.detail
        },
        steps() {
            const when = v => (v ? formatVnTime(v, { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '')
            return [
                { key: 'received', at: when(this.c.created_at) },
                { key: 'verifying', at: when(this.c.acknowledged_at) },
                { key: 'resolved', at: when(this.c.resolved_at) },
            ]
        },
        orderText() {
            return this.$t('complaints.order_label', { code: orderCode(this.c.order_id) })
        },
    },

    mounted() {
        this.store.loadDetail(this.$route.params.complaintId)
    },
}
</script>

<template>
    <div v-if="store.loadingDetail" class="detail">
        <q-skeleton type="rect" height="80px" style="border-radius:12px;" animation="pulse" />
        <q-skeleton type="rect" height="120px" style="border-radius:12px;" animation="pulse" />
    </div>

    <div v-else-if="!c" class="not-found">{{ $t('complaints.not_found') }}</div>

    <div v-else class="detail">
        <div class="card head">
            <div class="head-row">
                <div class="code">{{ c.code }}</div>
                <ComplaintStatusChip :status="c.status" />
            </div>
            <div class="sub">{{ orderText }} · {{ $t(`complaints.category.${c.category}`) }}</div>
            <div v-if="!c.is_mine" class="sub">{{ $t('complaints.from_buyer') }}</div>
        </div>

        <div class="card">
            <div v-for="s in steps" :key="s.key" class="step" :class="{ done: !!s.at }">
                <span class="dot" />
                <span class="step-label">{{ $t(`complaints.status.${s.key}`) }}</span>
                <span class="step-at">{{ s.at }}</span>
            </div>
        </div>

        <div class="card">
            <div class="label">{{ $t('complaints.field_description') }}</div>
            <div class="text">{{ c.description }}</div>
            <div v-if="c.images.length" class="photos">
                <a v-for="src in c.images" :key="src" :href="src" target="_blank" rel="noopener" class="photo">
                    <img :src="src" alt="" />
                </a>
            </div>
        </div>

        <div v-if="c.resolution" class="card resolution">
            <div class="label">{{ $t('complaints.resolution') }}</div>
            <div class="text">{{ c.resolution }}</div>
        </div>
    </div>
</template>

<style scoped>
.detail {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.head-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
}

.code {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: var(--text-primary);
}

.sub {
    font-size: 13px;
    color: var(--text-secondary);
}

.step {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
    color: var(--text-muted);
}

.step.done {
    color: var(--text-primary);
}

.dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 2px solid currentColor;
    flex-shrink: 0;
}

.step.done .dot {
    background: var(--color-accent);
    border-color: var(--color-accent);
}

.step-label {
    flex: 1;
}

.step-at {
    font-size: 12px;
    color: var(--text-secondary);
}

.label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

.text {
    font-size: 14px;
    color: var(--text-primary);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}

.photos {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 4px;
}

.photo {
    width: 84px;
    height: 84px;
    border-radius: 10px;
    overflow: hidden;
}

.photo img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.resolution {
    border-color: rgba(34, 197, 94, 0.3);
}

.not-found {
    text-align: center;
    padding: 32px 0;
    color: var(--text-secondary);
}
</style>
