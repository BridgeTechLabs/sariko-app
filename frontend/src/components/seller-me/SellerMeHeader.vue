<script>
import { Camera } from 'lucide-vue-next';
import { mapState } from 'pinia';
import { useAuthStore } from '@/stores/auth/authStore';
import { useDashboardStore } from '@/stores/seller/dashboardStore';

export default {
    name: 'SellerMeHeader',

    components: { Camera },

    computed: {
        ...mapState(useAuthStore, ['user']),
        ...mapState(useDashboardStore, ['sellerInfo']),

        initials() {
            if (!this.user?.fullName) return '?'
            return this.user.fullName.trim().charAt(0).toUpperCase()
        },

        storeName() {
            return this.sellerInfo?.store_name || this.user?.fullName || ''
        },
    },

    mounted() {
        if (!this.sellerInfo) useDashboardStore().fetchSellerInfo()
    },

    methods: {
        goEditProfile() {
            this.$router.push('/account/profile')
        },
    }
}
</script>

<template>
    <div class="seller-me-header">

        <!-- Avatar -->
        <div class="avatar-wrap" @click="goEditProfile">
            <q-avatar v-if="user?.avatarUrl" size="88px" class="avatar-img">
                <img :src="user.avatarUrl" :alt="storeName">
            </q-avatar>
            <div v-else class="avatar-initials">
                {{ initials }}
            </div>
            <div class="avatar-edit-badge">
                <Camera :size="12" />
            </div>
        </div>

        <!-- Store name + badge -->
        <div class="store-name">{{ storeName }}</div>
        <div class="store-email">{{ user?.email }}</div>

        <span class="seller-badge">{{ $t('seller_me.seller_badge') }}</span>

        <!-- Edit profile button -->
        <button class="edit-profile-btn" @click="goEditProfile">
            {{ $t('seller_me.edit_profile') }}
        </button>

    </div>
</template>

<style scoped>
.seller-me-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 8px 0 4px;
}

.avatar-wrap {
    position: relative;
    cursor: pointer;
    margin-bottom: 14px;
}

.avatar-img :deep(img) {
    object-fit: cover;
    width: 100%;
    height: 100%;
}

.avatar-initials {
    width: 88px;
    height: 88px;
    border-radius: 50%;
    background: rgba(245, 166, 35, 0.15);
    color: var(--color-accent);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 32px;
    font-weight: 700;
    border: 1px solid rgba(245, 166, 35, 0.3);
}

.avatar-edit-badge {
    position: absolute;
    bottom: 2px;
    right: 2px;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--color-accent);
    color: #000;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid var(--bg-main);
}

.store-name {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.store-email {
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 10px;
}

.seller-badge {
    font-size: 11px;
    font-weight: 600;
    padding: 3px 12px;
    border-radius: 12px;
    background: rgba(245, 166, 35, 0.15);
    color: var(--color-accent);
    margin-bottom: 14px;
}

.edit-profile-btn {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-accent);
    background: rgba(245, 166, 35, 0.1);
    border: 1px solid rgba(245, 166, 35, 0.3);
    border-radius: 20px;
    padding: 6px 20px;
    cursor: pointer;
}
</style>
