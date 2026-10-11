<script>
import { useI18n } from 'vue-i18n';
import { mapActions, mapState } from 'pinia';
import { useSellerStore } from '@/stores/seller/sellerStore';
import SellerCard from '@/components/seller/seller-list/SellerCard.vue';

export default {

    setup() {
        const {t, locale} = useI18n()
    },


    components: {
        SellerCard
    },

    computed: {
        ...mapState(useSellerStore, ["foundingSellers"]),
        previewSellers() {
            return this.foundingSellers.slice(0, 5)
        },
        hasMore() {
            return this.foundingSellers.length > 5
        }
    },

    methods: {
        ...mapActions(useSellerStore, [
            "getFoundingSellers"
        ])
    },

    created() {
        this.getFoundingSellers()
    }
}

</script>

<template>
    <div class="container">

        <div class="group-title">

            <div class="title">
                ⭐ {{ $t("home_page.section_founding_sellers.title") }}
            </div>
            <div class="button-see-all">
                <q-btn
                no-caps
                flat
                style="color: #bb8221; font-size: 12px; font-weight: 700;"
                :label="$t('home_page.section_founding_sellers.button_label_see_all')"
                @click="$router.push('/sellers')"
                />
            </div>

        </div>
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

        <!-- Real data -->
        <div v-else class="sellers-grid">
            <SellerCard
                v-for="(seller, index) in previewSellers"
                :key="seller.id"
                :seller-index="index+1"
                :seller-name="seller.store_name"
                :seller-slug-name="seller.slug"
                :seller-avatar-image-u-r-l="seller.avatar_url"
                :seller-featured-category="'Exclusive Dishes'"
                :seller-status="seller.status"
                :seller-is-open="seller.is_open !== false"
            />
            <!-- See All tile -->
            <div v-if="hasMore" class="see-all-tile" @click="$router.push('/sellers')">
                <span class="see-all-count">+{{ foundingSellers.length - 5 }}</span>
                <span class="see-all-label">{{ $t('home_page.section_founding_sellers.button_label_see_all') }}</span>
            </div>
        </div>

    </div>
    
</template>

<style lang="scss" scoped>
.container {
    font-family: $sariko-font-family-secondary;
}

.group-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 5px;
}

.title {
    font-size: 13px;
    font-weight: 700;
}

.sellers-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
}

.see-all-tile {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    border: 1.5px dashed rgba(245, 166, 35, 0.4);
    border-radius: .75rem;
    padding: 10px 14px;
    cursor: pointer;
    min-height: 68px;
}

.see-all-count {
    font-size: 18px;
    font-weight: 700;
    color: #f5a623;
}

.see-all-label {
    font-size: 9px;
    font-weight: 600;
    color: #bb8221;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.skeleton-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: .75rem;
}

.skeleton-text {
    display: flex;
    flex-direction: column;
}
</style>