<script>
import LayoutBaseTerms from '@/layouts/v2/account/LayoutBaseTerms.vue';
import TermsTopBar from '@/components/v2/account/terms/TermsTopBar.vue';
import TermsContent from '@/components/v2/account/terms/TermsContent.vue';

export default {
    name: 'TermsPageV2',
    components: {
        LayoutBaseTerms,
        TermsTopBar,
        TermsContent,
    }
}
</script>

<template>
    <LayoutBaseTerms>

        <template #TermsTopBar>
            <TermsTopBar />
        </template>

        <template #TermsContent>
            <TermsContent />
        </template>

    </LayoutBaseTerms>
</template>
