<script>
import LayoutBaseComplaint from '@/layouts/complaint/LayoutBaseComplaint.vue';
import PageBreadcrumbs from '@/components/shared/PageBreadcrumbs.vue';
import ComplaintDetail from '@/components/complaints/ComplaintDetail.vue';

export default {
    components: { LayoutBaseComplaint, PageBreadcrumbs, ComplaintDetail },
}
</script>

<template>
    <LayoutBaseComplaint>
        <template #Breadcrumbs>
            <PageBreadcrumbs :title="$t('complaints.title_detail')" />
        </template>
        <template #Content>
            <ComplaintDetail :key="$route.params.complaintId" />
        </template>
    </LayoutBaseComplaint>
</template>
