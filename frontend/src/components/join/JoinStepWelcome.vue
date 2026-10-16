<script>
export default {
    data() {
        return { points: ['point_1', 'point_2', 'point_3', 'point_4', 'point_5'] }
    },
}
</script>

<template>
    <div class="join-step">
        <div class="join-section-title">{{ $t('join_page.welcome_title') }}</div>
        <ul class="points">
            <li v-for="p in points" :key="p">{{ $t(`join_page.welcome_${p}`) }}</li>
        </ul>
        <a href="/docs/sariko_seller_guide.html" target="_blank" rel="noopener" class="join-link">
            {{ $t('join_page.welcome_guide_link') }}
        </a>
        <div class="join-card">
            <div class="join-label">{{ $t('join_page.welcome_prepare_title') }}</div>
            <ul class="points prepare">
                <li>{{ $t('join_page.welcome_prepare_id') }}</li>
                <li>{{ $t('join_page.welcome_prepare_photos') }}</li>
                <li>{{ $t('join_page.welcome_prepare_bank') }}</li>
            </ul>
        </div>
        <div class="join-hint">{{ $t('join_page.welcome_time') }}</div>
    </div>
</template>

<style lang="scss" scoped>
.points {
    margin: 0;
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 14px;
    line-height: 1.5;
}

.prepare {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.8);
}
</style>
