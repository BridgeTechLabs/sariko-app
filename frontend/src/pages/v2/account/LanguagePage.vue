<script>
import LayoutBaseLanguage from '@/layouts/v2/account/LayoutBaseLanguage.vue';
import LanguageTopBar from '@/components/v2/account/language/LanguageTopBar.vue';
import LanguageOptionList from '@/components/v2/account/language/LanguageOptionList.vue';

export default {
    name: 'LanguagePageV2',
    components: {
        LayoutBaseLanguage,
        LanguageTopBar,
        LanguageOptionList,
    }
}
</script>

<template>
    <LayoutBaseLanguage>

        <template #LanguageTopBar>
            <LanguageTopBar />
        </template>

        <template #LanguageOptionList>
            <LanguageOptionList />
        </template>

    </LayoutBaseLanguage>
</template>
