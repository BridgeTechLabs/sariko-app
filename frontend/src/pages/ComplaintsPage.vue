<script>
import LayoutBaseComplaint from '@/layouts/complaint/LayoutBaseComplaint.vue';
import PageBreadcrumbs from '@/components/shared/PageBreadcrumbs.vue';
import ComplaintList from '@/components/complaints/ComplaintList.vue';

export default {
    components: { LayoutBaseComplaint, PageBreadcrumbs, ComplaintList },
}
</script>

<template>
    <LayoutBaseComplaint>
        <template #Breadcrumbs>
            <PageBreadcrumbs :title="$t('complaints.title_mine')" />
        </template>
        <template #Content>
            <ComplaintList />
        </template>
    </LayoutBaseComplaint>
</template>
