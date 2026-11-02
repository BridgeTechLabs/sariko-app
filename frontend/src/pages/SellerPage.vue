<script>
import { mapState } from 'pinia';
import { useSellerStore } from '@/stores/seller/sellerStore';
import LayoutBaseSellerPage from '@/layouts/seller/LayoutBaseSellerPage.vue';
import SellerInfo from '@/components/seller/seller-page/SellerInfo.vue';
import Categories from '@/components/seller/seller-page/Categories.vue';
import Menu from '@/components/seller/seller-page/Menu.vue';
import SellerComingSoon from '@/components/seller/seller-page/SellerComingSoon.vue';
import CartFab from '@/components/seller/seller-page/CartFab.vue';
import SellerPageSkeleton from '@/components/seller/seller-page/SellerPageSkeleton.vue';

export default {
    components: {
        LayoutBaseSellerPage,
        SellerInfo,
        Categories,
        Menu,
        SellerComingSoon,
        SellerPageSkeleton,
        CartFab
    },

    computed: {
        ...mapState(useSellerStore, ['seller']),
        isComingSoon() {
            return this.seller?.status === 'coming_soon'
        }
    },

    mounted() {
        const sellerStore = useSellerStore()
        sellerStore.seller = null
        sellerStore.menus = []
        sellerStore.menuCategories = []
        sellerStore.selectedCategoryMenu = null
        const slugName = this.$route.params.slugName
        sellerStore.getSellerbySlugName(slugName)
    }
}
</script>

<template>

    <SellerPageSkeleton v-if="!seller" />

    <LayoutBaseSellerPage v-else>

        <template #SellerInfo>
            <SellerInfo />
        </template>

        <template #Categories>
            <Categories v-if="!isComingSoon" />
        </template>

        <template #Menu>
            <Menu v-if="!isComingSoon" />
            <SellerComingSoon v-else />
        </template>

        <template #CartFab>
            <CartFab v-if="!isComingSoon" />
        </template>

    </LayoutBaseSellerPage>

</template>

<style>
</style>