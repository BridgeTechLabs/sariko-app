<script>
import { User } from 'lucide-vue-next';
import { mapState } from 'pinia';
import { useAuthStore } from '@/stores/auth/authStore';
import { useDashboardStore } from '@/stores/seller/dashboardStore';

// Orders that still need the seller after closing: closing only stops new same-day orders
const ACTIVE_STATUSES = ['pending', 'confirmed', 'ready', 'delivery_failed']

export default {
    name: 'SellerGreeting',

    components: { User },

    data() {
        return {
            now: new Date(),
            ticker: null,
            hoursDialog: false,
            allDay: true,
            draftOpen: '10:00',
            draftClose: '20:00',
            savingHours: false,
        }
    },

    computed: {
        ...mapState(useAuthStore, ['user']),
        ...mapState(useDashboardStore, ['sellerInfo', 'orders']),

        isOpen() {
            return this.sellerInfo?.is_open !== false
        },

        // "10:00–20:00", or null when open all day
        hoursText() {
            const o = this.sellerInfo?.opening_time, c = this.sellerInfo?.closing_time
            return o && c ? `${o.slice(0, 5)}–${c.slice(0, 5)}` : null
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
        openHoursDialog() {
            this.allDay = !this.hoursText
            this.draftOpen = this.sellerInfo?.opening_time?.slice(0, 5) || '10:00'
            this.draftClose = this.sellerInfo?.closing_time?.slice(0, 5) || '20:00'
            this.hoursDialog = true
        },

        async saveHours() {
            this.savingHours = true
            try {
                await useDashboardStore().setStoreHours(this.allDay ? null : this.draftOpen, this.allDay ? null : this.draftClose)
                this.hoursDialog = false
            } catch (e) {
                console.error('SellerGreeting - saveHours -', e)
                this.$q.notify({ classes: 'quasar-notify-negative', message: this.$t('common.toast_update_failed'), position: 'bottom' })
            } finally {
                this.savingHours = false
            }
        },

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
            <q-toggle
                v-if="sellerInfo"
                :model-value="isOpen"
                :label="isOpen ? $t('seller_home.store_open') : $t('seller_home.store_closed')"
                color="positive"
                dense
                class="open-toggle"
                @update:model-value="onToggleOpen"
            />
            <div v-if="sellerInfo" class="hours-row">
                <span>{{ $t('seller_home.hours_label') }}: {{ hoursText || $t('seller_home.hours_all_day') }}</span>
                <button class="hours-edit" @click="openHoursDialog">{{ $t('seller_home.hours_edit') }}</button>
            </div>
            <div v-if="outsideHours" class="hours-hint">{{ $t('seller_home.hours_outside_hint') }}</div>

            <q-dialog v-model="hoursDialog">
                <q-card dark class="hours-dialog">
                    <q-card-section class="text-subtitle1">{{ $t('seller_home.hours_label') }}</q-card-section>
                    <q-card-section>
                        <q-toggle v-model="allDay" :label="$t('seller_home.hours_all_day')" color="positive" dense />
                        <div v-if="!allDay" class="hours-inputs">
                            <label>{{ $t('seller_home.hours_open_at') }} <input v-model="draftOpen" type="time" required></label>
                            <label>{{ $t('seller_home.hours_close_at') }} <input v-model="draftClose" type="time" required></label>
                            <div class="hours-note">{{ $t('seller_home.hours_overnight_note') }}</div>
                        </div>
                    </q-card-section>
                    <q-card-actions align="right">
                        <q-btn flat no-caps :label="$t('common.button_label_cancel')" v-close-popup />
                        <q-btn unelevated no-caps color="positive" :loading="savingHours"
                            :disable="!allDay && (!draftOpen || !draftClose)"
                            :label="$t('common.button_label_save')" @click="saveHours" />
                    </q-card-actions>
                </q-card>
            </q-dialog>
        </div>

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
    align-items:center;
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

.avatar-wrap {
    cursor: pointer;
    flex-shrink: 0;
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
    margin-top: 8px;
    font-size: 13px;
}

.hours-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 4px;
    font-size: 12px;
    opacity: 0.8;
}

.hours-edit {
    background: none;
    border: none;
    padding: 0;
    color: #f5A623;
    font-size: 12px;
    cursor: pointer;
}

.hours-hint {
    margin-top: 4px;
    font-size: 12px;
    color: #f5A623;
}

.hours-dialog {
    min-width: 280px;
}

.hours-inputs {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 14px;

    label {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
    }

    input {
        background: transparent;
        color: inherit;
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 8px;
        padding: 6px 8px;
        color-scheme: dark;
    }
}

.hours-note {
    font-size: 11px;
    opacity: 0.6;
}
</style>
