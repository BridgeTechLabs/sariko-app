<script>
import { mapState, mapActions } from 'pinia';
import { MapPin, Globe, FileText, Shield, Lock, Bell, ChevronRight, Receipt, MessageCircle, ExternalLink, UserCheck, MessageSquareWarning } from 'lucide-vue-next';
import { useAccountV2Store } from '@/stores/v2/account/accountStore';
import { useProfileCompletionStore } from '@/stores/seller/profileCompletionStore';
import BaseSwitch from '@/components/v2/shared/BaseSwitch.vue';
import { SUPPORT_EMAIL, SUPPORT_MAILTO } from '@/utils/support';

export default {
    name: 'SellerMeSettings',

    components: { MapPin, Globe, FileText, Shield, Lock, Bell, ChevronRight, Receipt, MessageCircle, ExternalLink, UserCheck, MessageSquareWarning, BaseSwitch },

    data() {
        return { supportEmail: SUPPORT_EMAIL, supportMailto: SUPPORT_MAILTO }
    },

    computed: {
        ...mapState(useAccountV2Store, ['notifications']),
        ...mapState(useProfileCompletionStore, { profileMissing: 'missing' }),
    },

    methods: {
        ...mapActions(useAccountV2Store, ['togglePush', 'syncPushState']),
        ...mapActions(useProfileCompletionStore, { fetchProfileCompletion: 'fetch' }),
    },

    mounted() {
        this.syncPushState()
        this.fetchProfileCompletion()
    },
}
</script>

<template>
    <div>
        <div class="section-title">{{ $t('seller_me.section_title_settings') }}</div>
        <div class="menu-group">

            <div class="menu-item" @click="togglePush">
                <div class="menu-icon"><Bell size="18" /></div>
                <span class="menu-label">{{ $t('seller_me.menu_label_new_order_alerts') }}</span>
                <!-- No v-model: the click bubbles up to the row, which toggles -->
                <BaseSwitch :model-value="notifications.orderUpdates" :label="$t('seller_me.menu_label_new_order_alerts')" />
            </div>

            <router-link to="/seller/me/profile" class="menu-item">
                <div class="menu-icon"><UserCheck size="18" /></div>
                <span class="menu-label">{{ $t('seller_profile.menu_label') }}</span>
                <span v-if="profileMissing.length" class="missing-dot" :aria-label="$t('seller_profile.menu_missing', { n: profileMissing.length })">{{ profileMissing.length }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </router-link>

            <router-link to="/account/address" class="menu-item">
                <div class="menu-icon"><MapPin size="18" /></div>
                <span class="menu-label">{{ $t('seller_me.menu_label_store_address') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </router-link>

            <router-link to="/account/language" class="menu-item">
                <div class="menu-icon"><Globe size="18" /></div>
                <span class="menu-label">{{ $t('seller_me.menu_label_language') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </router-link>

            <router-link to="/account/change-password" class="menu-item">
                <div class="menu-icon"><Lock size="18" /></div>
                <span class="menu-label">{{ $t('account_page.menu_label_change_password') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </router-link>

            <router-link to="/complaints" class="menu-item">
                <div class="menu-icon"><MessageSquareWarning size="18" /></div>
                <span class="menu-label">{{ $t('complaints.menu_label') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </router-link>

            <a :href="supportMailto" class="menu-item">
                <div class="menu-icon"><MessageCircle size="18" /></div>
                <span class="menu-label">{{ $t('seller_me.menu_label_support') }}<span class="menu-sub">{{ supportEmail }}</span></span>
                <ExternalLink size="14" class="menu-arrow" />
            </a>

            <a href="/docs/sariko_seller_agreement.html" target="_blank" class="menu-item">
                <div class="menu-icon"><FileText size="18" /></div>
                <span class="menu-label">{{ $t('seller_me.menu_label_seller_agreement') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </a>

            <a href="/docs/privacy-policy.html" target="_blank" class="menu-item">
                <div class="menu-icon"><Shield size="18" /></div>
                <span class="menu-label">{{ $t('seller_me.menu_label_privacy') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </a>

            <a href="/docs/sariko_fees.html" target="_blank" class="menu-item">
                <div class="menu-icon"><Receipt size="18" /></div>
                <span class="menu-label">{{ $t('seller_me.menu_label_fees') }}</span>
                <ChevronRight size="16" class="menu-arrow" />
            </a>

        </div>
    </div>
</template>

<style scoped>
.section-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
    padding-left: 4px;
}

.menu-group {
    background: rgb(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
}

.menu-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    cursor: pointer;
    text-decoration: none;
    color: var(--text-primary);
    transition: background 0.15s ease;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.menu-sub {
    display: block;
    font-size: 12px;
    color: var(--text-secondary);
}

.menu-item:last-child {
    border-bottom: none;
}

.menu-item:hover {
    background: var(--bg-card-hover);
}

.menu-icon {
    width: 24px;
    height: 24px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.05);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
    flex-shrink: 0;
}

.menu-label {
    flex: 1;
    font-size: 14px;
    font-weight: 500;
}

.missing-dot {
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    border-radius: 10px;
    background: var(--color-error);
    color: #fff;
    font-size: 12px;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
}

.menu-arrow {
    color: var(--text-muted);
}
</style>
