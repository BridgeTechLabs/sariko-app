<script>
import { mapState } from 'pinia'
import { useDashboardStore } from '@/stores/seller/dashboardStore'
import { WEEK_KEYS, vnWeekdayKey, weekdayName } from '@/utils/vnTime'

const NEW_DAY = { open: '10:00', close: '20:00' }

export default {
    name: 'SellerWeeklyHours',

    data() {
        return {
            allDay: false,
            week: null,      // { "1".."7": { open, close } | null (day off) }, edited locally until Save
            saving: false,
            keys: WEEK_KEYS,
            today: vnWeekdayKey(),
        }
    },

    computed: {
        ...mapState(useDashboardStore, ['sellerInfo']),

        errors() {
            return Object.fromEntries(this.keys.map(k => {
                const d = this.week?.[k]
                if (!d) return [k, null]
                if (!d.open || !d.close) return [k, this.$t('seller_hours.error_missing')]
                return [k, d.open === d.close ? this.$t('seller_hours.error_same') : null]
            }))
        },

        hasErrors() {
            return !this.allDay && Object.values(this.errors).some(Boolean)
        },
    },

    async created() {
        if (!this.sellerInfo) await useDashboardStore().fetchSellerInfo()
        const saved = this.sellerInfo?.weekly_hours
        this.allDay = !saved
        this.week = Object.fromEntries(this.keys.map(k => [k, saved ? saved[k] && { ...saved[k] } : { ...NEW_DAY }]))
    },

    methods: {
        dayName: weekdayName,

        setOpen(key, open) {
            this.week[key] = open ? { ...NEW_DAY } : null
        },

        copyMonday(keys) {
            for (const k of keys) this.week[k] = this.week['1'] && { ...this.week['1'] }
        },

        async save() {
            if (this.hasErrors) return
            this.saving = true
            try {
                await useDashboardStore().setStoreHours(this.allDay ? null : { ...this.week })
                this.$q.notify({ classes: 'quasar-notify-positive', message: this.$t('seller_hours.saved'), position: 'bottom' })
            } catch (e) {
                console.error('SellerWeeklyHours - save -', e)
                this.$q.notify({ classes: 'quasar-notify-negative', message: this.$t('common.toast_update_failed'), position: 'bottom' })
            } finally {
                this.saving = false
            }
        },
    },
}
</script>

<template>
    <div class="weekly-hours">
        <template v-if="!week">
            <q-skeleton v-for="n in 4" :key="n" animation="pulse" height="96px" class="day-card" />
        </template>

        <template v-else>
            <q-btn-toggle
                v-model="allDay"
                spread no-caps unelevated
                toggle-color="positive" color="dark" text-color="grey-5"
                class="mode"
                :options="[{ label: $t('seller_hours.mode_weekly'), value: false }, { label: $t('seller_hours.mode_all_day'), value: true }]"
            />

            <div v-if="allDay" class="allday-note">{{ $t('seller_hours.all_day_note') }}</div>

            <template v-else>
                <div v-for="k in keys" :key="k" class="day-card" :class="{ today: k === today }">
                    <div class="day-head">
                        <span class="day-name">
                            {{ dayName(k) }}
                            <span v-if="k === today" class="chip">{{ $t('seller_hours.today') }}</span>
                            <span v-if="week[k] && week[k].close < week[k].open" class="chip">{{ $t('seller_hours.overnight') }}</span>
                        </span>
                        <q-toggle
                            :model-value="!!week[k]"
                            :label="week[k] ? $t('seller_hours.open') : $t('seller_hours.day_off')"
                            left-label dense color="positive"
                            @update:model-value="setOpen(k, $event)"
                        />
                    </div>

                    <div v-if="!week[k]" class="rest">{{ $t('seller_hours.day_off_note') }}</div>
                    <template v-else>
                        <div class="range">
                            <input v-model="week[k].open" type="time" :aria-label="$t('seller_hours.aria_opens', { day: dayName(k) })">
                            <span class="dash">–</span>
                            <input v-model="week[k].close" type="time" :aria-label="$t('seller_hours.aria_closes', { day: dayName(k) })">
                        </div>
                        <div v-if="errors[k]" class="error">{{ errors[k] }}</div>
                    </template>

                    <div v-if="k === '1'" class="copy-row">
                        <button class="link" @click="copyMonday(['2', '3', '4', '5'])">{{ $t('seller_hours.copy_weekdays') }}</button>
                        <button class="link" @click="copyMonday(['2', '3', '4', '5', '6', '7'])">{{ $t('seller_hours.copy_all') }}</button>
                    </div>
                </div>

                <div class="hint">{{ $t('seller_hours.hint') }}</div>
            </template>

            <q-btn unelevated no-caps color="positive" class="save" :label="$t('common.button_label_save')"
                :loading="saving" :disable="hasErrors" @click="save" />
        </template>
    </div>
</template>

<style lang="scss" scoped>
.weekly-hours {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-bottom: calc(var(--bottom-nav-height, 72px) + 8px);
    color: var(--text-primary);
}

.mode {
    border: 1px solid var(--border-color);
    border-radius: 10px;
    margin-bottom: 6px;
}

.allday-note,
.day-card {
    background: var(--bg-surface);
    border-radius: 12px;
    padding: 12px 14px;
}

.allday-note {
    color: var(--text-muted);
    line-height: 1.5;
}

.day-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    border: 1px solid transparent;
}

.day-card.today {
    border-color: rgba(245, 166, 35, 0.5);
}

.day-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.day-name {
    font-size: 15px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
}

.chip {
    font-size: 11px;
    font-weight: 600;
    color: #f5A623;
    background: rgba(245, 166, 35, 0.15);
    padding: 2px 8px;
    border-radius: 999px;
}

.rest {
    color: var(--text-muted);
    font-size: 13px;
}

.range {
    display: flex;
    align-items: center;
    gap: 8px;
}

.range input {
    flex: 1 1 0;
    min-width: 0;
    background: var(--bg-surface-2);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-primary);
    color-scheme: dark;
    padding: 8px 10px;
    font-size: 15px;
    font-variant-numeric: tabular-nums;
}

.dash {
    color: var(--text-muted);
}

.error {
    color: #ef4444;
    font-size: 12px;
}

.link {
    align-self: flex-start;
    background: none;
    border: none;
    padding: 2px 0;
    color: #f5A623;
    font-size: 13px;
    cursor: pointer;
}

.copy-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 18px;
}

.hint {
    color: var(--text-muted);
    font-size: 12px;
    line-height: 1.5;
    padding: 0 2px;
}

.save {
    margin-top: 6px;
    min-height: 46px;
    border-radius: 10px;
    font-weight: 600;
}
</style>
