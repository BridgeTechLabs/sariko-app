<script>
import LayoutSellerMenu from '@/layouts/seller/LayoutSellerMenu.vue'
import SellerMenuList from '@/components/seller-menu/SellerMenuList.vue'
import PageBreadcrumbs from '@/components/shared/PageBreadcrumbs.vue'

export default {
    name: 'SellerMenuPage',

    components: { LayoutSellerMenu, SellerMenuList, PageBreadcrumbs },
}
</script>

<template>
    <LayoutSellerMenu>
        <template #Header>
            <PageBreadcrumbs :title="$t('seller_menu.page_title')" />
        </template>

        <template #Content>
            <SellerMenuList />
        </template>
    </LayoutSellerMenu>
</template>
