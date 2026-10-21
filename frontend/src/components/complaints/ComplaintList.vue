<script>
import { ChevronRight, MessageSquare } from 'lucide-vue-next';
import ComplaintStatusChip from '@/components/complaints/ComplaintStatusChip.vue';
import { useComplaintStore } from '@/stores/complaint/complaintStore';
import { orderCode } from '@/utils/orderCode';
import { formatVnTime } from '@/utils/vnTime';

// T35: the complaints the signed-in user filed, newest first.
export default {
    components: { ChevronRight, MessageSquare, ComplaintStatusChip },

    computed: {
        store() {
            return useComplaintStore()
        },
        rows() {
            return this.store.mine.map(c => ({
                ...c,
                orderText: this.$t('complaints.order_label', { code: orderCode(c.order_id) }),
                dateText: formatVnTime(c.created_at, { day: '2-digit', month: '2-digit', year: 'numeric' }),
            }))
        },
    },

    mounted() {
        this.store.loadMine()
    },
}
</script>

<template>
    <div v-if="store.loadingMine && !rows.length" class="list">
        <q-skeleton v-for="i in 3" :key="i" type="rect" height="64px" style="border-radius:12px;" animation="pulse" />
    </div>

    <div v-else-if="!rows.length" class="empty">
        <MessageSquare :size="28" class="empty-icon" />
        <div class="empty-text">{{ $t('complaints.empty') }}</div>
        <div class="empty-sub">{{ $t('complaints.empty_sub') }}</div>
    </div>

    <div v-else class="list">
        <router-link v-for="c in rows" :key="c.id" :to="`/complaints/${c.id}`" class="item">
            <div class="row-main">
                <div class="row-code">{{ c.code }} · {{ $t(`complaints.category.${c.category}`) }}</div>
                <div class="row-sub">{{ c.orderText }} · {{ c.dateText }}</div>
                <div v-if="c.resolution" class="row-resolution">{{ c.resolution }}</div>
            </div>
            <ComplaintStatusChip :status="c.status" />
            <ChevronRight :size="16" class="row-arrow" />
        </router-link>
    </div>
</template>

<style scoped>
.list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    text-decoration: none;
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

.row-resolution {
    margin-top: 4px;
    font-size: 12px;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.row-arrow {
    color: var(--text-muted);
    flex-shrink: 0;
}

.empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 32px 0;
    text-align: center;
}

.empty-icon {
    color: var(--color-accent);
    opacity: 0.6;
}

.empty-text {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
}

.empty-sub {
    font-size: 13px;
    color: var(--text-secondary);
}
</style>
