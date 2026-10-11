<script>
import LayoutBaseSettings from '@/layouts/account/LayoutBaseSettings.vue';
import SellerCard from '@/components/seller/seller-list/SellerCard.vue';
import { mapState, mapActions } from 'pinia';
import { useSellerStore } from '@/stores/seller/sellerStore';

export default {
    name: 'AllSellersPage',
    components: { LayoutBaseSettings, SellerCard },

    computed: {
        ...mapState(useSellerStore, ['foundingSellers'])
    },

    methods: {
        ...mapActions(useSellerStore, ['getFoundingSellers'])
    },

    mounted() {
        if (this.foundingSellers.length === 0) {
            this.getFoundingSellers()
        }
    }
}
</script>

<template>
    <LayoutBaseSettings title="⭐ Founding Sellers" back-to="/home">
        <template #Content>

            <!-- Skeleton -->
            <div v-if="foundingSellers.length === 0" class="sellers-grid">
                <div v-for="i in 6" :key="i" class="skeleton-card">
                    <q-skeleton type="circle" size="48px" animation="pulse" />
                    <div class="skeleton-text">
                        <q-skeleton type="text" width="80px" height="10px" animation="pulse" />
                        <q-skeleton type="text" width="60px" height="8px" animation="pulse" style="margin-top: 4px;" />
                    </div>
                </div>
            </div>

            <!-- All sellers -->
            <div v-else class="sellers-grid">
                <SellerCard
                    v-for="(seller, index) in foundingSellers"
                    :key="seller.id"
                    :seller-index="index + 1"
                    :seller-name="seller.store_name"
                    :seller-slug-name="seller.slug"
                    :seller-avatar-image-u-r-l="seller.avatar_url"
                    :seller-featured-category="'Exclusive Dishes'"
                    :seller-status="seller.status"
                    :seller-is-open="seller.is_open !== false"
                />
            </div>

        </template>
    </LayoutBaseSettings>
</template>

<style scoped>
.sellers-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
}

.skeleton-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
}

.skeleton-text {
    display: flex;
    flex-direction: column;
}
</style>
