<script>
import { User } from 'lucide-vue-next';
import { mapState } from 'pinia';
import { useAuthStore } from '@/stores/auth/authStore';
import { useDashboardStore } from '@/stores/seller/dashboardStore';
import { vnWeekdayKey } from '@/utils/vnTime';

// Orders that still need the seller after closing: closing only stops new same-day orders
const ACTIVE_STATUSES = ['pending', 'confirmed', 'ready', 'delivery_failed']

export default {
    name: 'SellerGreeting',

    components: { User },

    data() {
        return {
            now: new Date(),
            ticker: null,
        }
    },

    computed: {
        ...mapState(useAuthStore, ['user']),
        ...mapState(useDashboardStore, ['sellerInfo', 'orders']),

        isOpen() {
            return this.sellerInfo?.is_open !== false
        },

        // Today's hours (Vietnam time): "Today 10:00–20:00", "Closed today", or all day
        hoursText() {
            const week = this.sellerInfo?.weekly_hours
            if (!week) return this.$t('seller_home.hours_all_day')
            const today = week[vnWeekdayKey()]
            return today ? this.$t('seller_home.hours_today', { open: today.open, close: today.close }) : this.$t('seller_home.hours_today_off')
        },

        // Switch on but outside the hours: buyers see the store as closed
        outsideHours() {
            return this.isOpen && this.sellerInfo?.open_now === false
        },

        activeOrderCount() {
            return this.orders.filter(o => ACTIVE_STATUSES.includes(o.status)).length
        },

        greetingPrefix() {
            const hour = this.now.getHours()
            if (hour < 12) return this.$t('seller_home.greeting_morning_prefix')
            if (hour < 18) return this.$t('seller_home.greeting_afternoon_prefix')
            return this.$t('seller_home.greeting_evening_prefix')
        },

        greetingName() {
            return (this.user?.fullName || '...') + ' 👋'
        },

        initials() {
            if (!this.user?.fullName) return ''
            return this.user.fullName.trim().charAt(0).toUpperCase()
        },

        dateLocale() {
            return this.$i18n.locale === 'vi' ? 'vi-VN' : 'en-PH'
        },

        dateText() {
            return this.now.toLocaleDateString(this.dateLocale, {
                weekday: 'long',
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
            })
        },

        timeText() {
            return this.now.toLocaleTimeString(this.dateLocale, {
                hour: '2-digit',
                minute: '2-digit',
            })
        },
    },

    mounted() {
        this.ticker = setInterval(() => { this.now = new Date() }, 60000)
    },

    beforeUnmount() {
        clearInterval(this.ticker)
    },

    methods: {
        async onToggleOpen(open) {
            if (!open && this.activeOrderCount) {
                const confirmed = await new Promise(resolve => {
                    this.$q.dialog({
                        title: this.$t('seller_home.close_confirm_title'),
                        message: this.$t('seller_home.close_confirm_body', { count: this.activeOrderCount }),
                        cancel: true,
                        dark: true,
                    }).onOk(() => resolve(true)).onCancel(() => resolve(false))
                })
                if (!confirmed) return
            }
            try {
                await useDashboardStore().setStoreOpen(open)
            } catch (e) {
                console.error('SellerGreeting - onToggleOpen -', e)
                this.$q.notify({ classes: 'quasar-notify-negative', message: this.$t('common.toast_update_failed'), position: 'bottom' })
            }
        },
    },
}
</script>

<template>
    <div class="greeting-header">
        <div class="greeting-wrap">
            <div class="greeting-prefix">{{ greetingPrefix }}</div>
            <div class="greeting">{{ greetingName }}</div>
            <div v-if="sellerInfo?.store_name" class="store-line">{{ sellerInfo.store_name }}</div>
            <div class="datetime">
                <span class="date-text">{{ dateText }}</span>
                <span class="time-text">{{ timeText }}</span>
            </div>
            <div v-if="outsideHours" class="hours-hint">{{ $t('seller_home.hours_outside_hint') }}</div>
        </div>

        <!-- Right column like the buyer header's .user-column: avatar, open switch, hours -->
        <div class="user-column">
            <div class="avatar-wrap" @click="$router.push('/seller/me')">
                <q-avatar v-if="user?.avatarUrl" size="64px">
                    <img :src="user.avatarUrl" :alt="user.fullName">
                </q-avatar>
                <div v-else-if="user" class="initials-avatar">
                    {{ initials }}
                </div>
                <div v-else class="guest-icon">
                    <User :size="24" />
                </div>
            </div>
            <q-toggle
                v-if="sellerInfo"
                :model-value="isOpen"
                :label="isOpen ? $t('seller_home.store_open') : $t('seller_home.store_closed')"
                color="positive"
                dense
                class="open-toggle"
                @update:model-value="onToggleOpen"
            />
            <button v-if="sellerInfo" class="hours-row" :aria-label="$t('seller_home.hours_edit')" @click="$router.push({ name: 'seller-opening-hours' })">
                {{ hoursText }}
            </button>
        </div>
    </div>
</template>

<style lang="scss" scoped>
.store-line {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-accent);
    margin-top: 2px;
}

.greeting-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
}

.greeting-wrap {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
    min-width: 0;
}

.greeting-prefix {
    font-size: 13px;
    color: var(--text-secondary);
    font-family: $sariko-font-family-secondary;
}

.greeting {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
    word-break: break-word;
}

.datetime {
    display: flex;
    align-items: center;
    gap: 8px;
}

.date-text {
    font-size: 13px;
    color: var(--text-secondary);
    text-transform: capitalize;
}

.time-text {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-accent);
}

.user-column {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}

.avatar-wrap {
    cursor: pointer;
}

.avatar-wrap :deep(img) {
    object-fit: cover;
    width: 100%;
    height: 100%;
}

.initials-avatar {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: rgba(245, 166, 35, 0.2);
    border: 1px solid rgba(245, 166, 35, 0.3);
    color: #f5a623;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: 700;
    font-family: $sariko-font-family-primary;
}

.guest-icon {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    border: 1px solid rgba(255, 255, 255, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(255, 255, 255, 0.6);
}

.open-toggle {
    font-size: 13px;
    white-space: nowrap;
}

.hours-row {
    background: none;
    border: none;
    padding: 0;
    color: #f5A623;
    font-size: 12px;
    white-space: nowrap;
    cursor: pointer;
}

.hours-hint {
    margin-top: 4px;
    font-size: 12px;
    color: #f5A623;
}
</style>
