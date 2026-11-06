<script>
import LayoutBaseSettings from '@/layouts/account/LayoutBaseSettings.vue'
import SellerWeeklyHours from '@/components/seller-hours/SellerWeeklyHours.vue'

export default {
    name: 'SellerHoursPage',
    components: { LayoutBaseSettings, SellerWeeklyHours },
}
</script>

<template>
    <LayoutBaseSettings :title="$t('seller_hours.page_title')" back-to="/seller/home">
        <template #Content>
            <SellerWeeklyHours />
        </template>
    </LayoutBaseSettings>
</template>
