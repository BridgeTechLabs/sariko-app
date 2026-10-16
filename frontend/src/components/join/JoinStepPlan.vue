<script>
import { useJoinStore } from '@/stores/join/joinStore'

export default {
    computed: {
        store() {
            return useJoinStore()
        },
    },

    methods: {
        vnd(amount) {
            return new Intl.NumberFormat('vi-VN').format(amount) + ' ₫'
        },
    },
}
</script>

<template>
    <div class="join-step">
        <div class="join-hint">{{ $t('join_page.plan_hint') }}</div>

        <div class="tiers">
            <button
                v-for="t in store.tiers"
                :key="t.id"
                type="button"
                class="tier"
                :class="{ 'tier--active': store.form.tier === t.id }"
                @click="store.form.tier = t.id"
            >
                <div class="tier-name">
                    {{ $t(`join_page.tier_${t.id}`) }}
                    <span v-if="t.invite" class="badge">{{ $t('join_page.plan_by_invitation') }}</span>
                </div>
                <div class="tier-fee">
                    {{ t.monthlyFee ? vnd(t.monthlyFee) : $t('join_page.plan_free') }}
                    <span v-if="t.monthlyFee" class="per">{{ $t('join_page.plan_per_month') }}</span>
                </div>
                <div class="tier-line">{{ $t('join_page.plan_commission', { rate: t.commission }) }}</div>
                <div class="tier-line">
                    {{ t.maxItems === null ? $t('join_page.plan_unlimited') : $t('join_page.plan_limits', { items: t.maxItems, categories: t.maxCategories }) }}
                </div>
            </button>
        </div>

        <div class="join-hint">{{ $t('join_page.plan_vat_note') }}</div>

        <q-checkbox v-model="store.form.founding_invited" dark dense color="amber" :label="$t('join_page.plan_founding')" />
        <div class="join-hint">{{ $t('join_page.plan_founding_hint', store.founding) }}</div>

        <a href="/docs/sariko_fees.html" target="_blank" rel="noopener" class="join-link">{{ $t('join_page.plan_fees_link') }}</a>
    </div>
</template>

<style lang="scss" scoped>
.tiers {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 10px;
}

.tier {
    text-align: left;
    background: #1f2940;
    border: 2px solid transparent;
    border-radius: 16px;
    padding: 14px;
    color: #fff;
    font-family: inherit;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.tier--active {
    border-color: #f5a623;
    background: rgba(245, 166, 35, 0.08);
}

.tier-name {
    font-weight: 700;
    font-size: 15px;
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
}

.badge {
    font-size: 10px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.12);
}

.tier-fee {
    font-size: 18px;
    font-weight: 700;
    color: #f5a623;
}

.per {
    font-size: 12px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.6);
}

.tier-line {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.75);
}
</style>
