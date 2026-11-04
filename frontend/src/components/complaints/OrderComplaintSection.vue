<script>
import { ChevronRight } from 'lucide-vue-next';
import ComplaintStatusChip from '@/components/complaints/ComplaintStatusChip.vue';
import { useOrderStore } from '@/stores/order/orderStore.js';
import { useDashboardStore } from '@/stores/seller/dashboardStore';

// T35, on the order detail screen of the buyer (own complaints) or the seller (the buyer's and own).
// complaints + can_complain come with the order detail, so the order poll keeps them fresh.
export default {
    components: { ChevronRight, ComplaintStatusChip },

    props: {
        role: { type: String, required: true },   // buyer | seller: which order store holds the order
    },

    computed: {
        order() {
            return this.role === 'seller' ? useDashboardStore().orderDetails : useOrderStore().currentOrder
        },
        complaints() {
            return this.order?.complaints || []
        },
    },

    methods: {
        open(c) {
            this.$router.push(`/complaints/${c.id}`)
        },
        fileNew() {
            this.$router.push({ path: '/complaints/new', query: { order: this.order.id, as: this.role } })
        },
    },
}
</script>

<template>
    <div v-if="order && (complaints.length || order.can_complain)" class="complaint-section">
        <div class="section-title">{{ $t('complaints.section_title') }}</div>

        <div v-for="c in complaints" :key="c.id" class="complaint-row" @click="open(c)">
            <div class="row-main">
                <div class="row-code">{{ c.code }} · {{ $t(`complaints.category.${c.category}`) }}</div>
                <div class="row-sub">{{ $t(c.is_mine ? 'complaints.from_me' : 'complaints.from_buyer') }}</div>
            </div>
            <ComplaintStatusChip :status="c.status" />
            <ChevronRight :size="16" class="row-arrow" />
        </div>

        <q-btn v-if="order.can_complain" class="btn-complain" flat dense no-caps @click="fileNew">
            {{ $t('complaints.btn_new') }}
        </q-btn>
    </div>
</template>

<style scoped>
.complaint-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 100%;
}

.section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

.complaint-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    cursor: pointer;
}

.row-main {
    flex: 1;
    min-width: 0;
}

.row-code {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

.row-sub {
    font-size: 12px;
    color: var(--text-secondary);
}

.row-arrow {
    color: var(--text-muted);
    flex-shrink: 0;
}

.btn-complain {
    width: 100%;
    padding: 12px 0;
    border-radius: 2rem;
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: var(--text-secondary);
    font-weight: 600;
}
</style>
