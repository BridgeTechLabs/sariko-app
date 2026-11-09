<script>
// The (i) button in the storefront's top-right corner and the "store info" sheet it opens: full name, address, weekly hours.
import { mapState } from 'pinia'
import { Info, X, MapPin, UtensilsCrossed, Clock, BadgeCheck } from 'lucide-vue-next'
import { useSellerStore } from '@/stores/seller/sellerStore'
import { WEEK_KEYS, vnWeekdayKey, weekdayName } from '@/utils/vnTime'

export default {
    name: 'SellerInfoSheet',
    components: { Info, X, MapPin, UtensilsCrossed, Clock, BadgeCheck },

    data() {
        return { show: false, keys: WEEK_KEYS, today: vnWeekdayKey() }
    },

    computed: {
        ...mapState(useSellerStore, ['seller', 'totalItems']),
    },

    methods: {
        dayName: weekdayName,
    },
}
</script>

<template>
    <button class="info-btn" :aria-label="$t('seller_page.aria_info')" @click="show = true"><Info :size="18" /></button>

    <q-dialog v-model="show" position="bottom">
        <div class="sheet" role="dialog" :aria-label="$t('seller_page.aria_info')">
            <div class="sheet-head">
                <div class="title">
                    <span>{{ seller?.store_name }}</span>
                    <BadgeCheck v-if="seller?.is_verified" :size="18" class="verified" />
                </div>
                <button class="close" :aria-label="$t('seller_page.aria_close')" @click="show = false"><X :size="20" /></button>
            </div>
            <q-badge v-if="seller?.is_founding" rounded class="founding">{{ $t('seller_page.founding_seller') }}</q-badge>

            <div class="line">
                <UtensilsCrossed :size="18" class="ic" />
                <span>{{ $t('seller_page.item_count', totalItems, { count: totalItems }) }}</span>
            </div>
            <p v-if="seller?.description?.trim()" class="desc">{{ seller.description }}</p>
            <div class="line">
                <MapPin :size="18" class="ic" />
                <span>{{ seller?.address || $t('seller_page.info_no_address') }}</span>
            </div>

            <div class="line">
                <Clock :size="18" class="ic" />
                <span class="sub">{{ $t('seller_page.info_hours') }}</span>
                <span class="state" :class="seller?.is_open ? 'open' : 'closed'">
                    {{ seller?.is_open ? $t('seller_page.info_open_now') : $t('seller_page.info_closed_now') }}
                </span>
            </div>
            <ul class="week">
                <li v-if="!seller?.weekly_hours" class="today">{{ $t('seller_page.info_all_day') }}</li>
                <template v-else>
                    <li v-for="k in keys" :key="k" :class="{ today: k === today }">
                        <span>{{ dayName(k) }}<span v-if="k === today" class="chip">{{ $t('seller_page.info_today') }}</span></span>
                        <span v-if="seller.weekly_hours[k]" class="t">{{ seller.weekly_hours[k].open }} – {{ seller.weekly_hours[k].close }}</span>
                        <span v-else class="off">{{ $t('seller_page.info_day_off') }}</span>
                    </li>
                </template>
            </ul>
            <div class="note">{{ $t('seller_page.info_preorder_note') }}</div>
        </div>
    </q-dialog>
</template>

<style lang="scss" scoped>
.info-btn {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: none;
    background: rgba(18, 27, 47, 0.55);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    color: #fff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.sheet {
    width: 100%;
    max-width: 480px;
    background: var(--bg-surface);
    color: var(--text-primary);
    border-radius: 18px 18px 0 0;
    padding: 18px 18px calc(18px + env(safe-area-inset-bottom, 0));
    display: flex;
    flex-direction: column;
    gap: 12px;
    font-family: $sariko-font-family-secondary;
}

.sheet-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
}

.title {
    font-size: 18px;
    font-weight: 700;
    line-height: 1.3;
    word-break: break-word;
    min-width: 0;
}

.verified {
    color: #3b82f6;
    vertical-align: -3px;
    margin-left: 4px;
}

.close {
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: none;
    background: var(--bg-surface-2);
    color: var(--text-primary);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.founding {
    align-self: flex-start;
    background: linear-gradient(90deg, #f5A623, #facc15);
    color: #121b2f;
    font-weight: 700;
    padding: 4px 10px;
}

.desc {
    margin: 0;
    font-size: 14px;
    line-height: 1.45;
    color: var(--text-muted);
    white-space: pre-line;
    overflow-wrap: anywhere;
}

.line {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    font-size: 14px;
    line-height: 1.45;
}

.ic {
    flex-shrink: 0;
    color: #f5A623;
    margin-top: 1px;
}

.sub {
    flex: 1;
    font-weight: 600;
}

.state {
    font-size: 12px;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 999px;
}

.state.open {
    background: rgba(16, 185, 129, 0.15);
    color: #10b981;
}

.state.closed {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
}

.week {
    list-style: none;
    margin: -4px 0 0;
    padding: 0 0 0 28px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 14px;
}

.week li {
    display: flex;
    justify-content: space-between;
    color: var(--text-muted);
}

.week li.today {
    color: var(--text-primary);
    font-weight: 600;
}

.t {
    font-variant-numeric: tabular-nums;
}

.off {
    color: #ef4444;
}

.chip {
    margin-left: 8px;
    font-size: 11px;
    color: #f5A623;
    background: rgba(245, 166, 35, 0.15);
    padding: 1px 8px;
    border-radius: 999px;
}

.note {
    font-size: 12px;
    color: var(--text-muted);
    padding-left: 28px;
}
</style>
