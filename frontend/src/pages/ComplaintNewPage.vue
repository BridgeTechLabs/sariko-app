<script>
import LayoutBaseComplaint from '@/layouts/complaint/LayoutBaseComplaint.vue';
import PageBreadcrumbs from '@/components/shared/PageBreadcrumbs.vue';
import ComplaintForm from '@/components/complaints/ComplaintForm.vue';
import { useComplaintStore } from '@/stores/complaint/complaintStore';

export default {
    components: { LayoutBaseComplaint, PageBreadcrumbs, ComplaintForm },

    mounted() {
        const store = useComplaintStore()
        store.resetForm()   // a draft from another order must not carry over
        store.loadConfig()
    },

    beforeUnmount() {
        useComplaintStore().resetForm()
    },
}
</script>

<template>
    <LayoutBaseComplaint>
        <template #Breadcrumbs>
            <PageBreadcrumbs :title="$t('complaints.title_new')" />
        </template>
        <template #Content>
            <ComplaintForm />
        </template>
    </LayoutBaseComplaint>
</template>
