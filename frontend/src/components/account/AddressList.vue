<script>
import { Briefcase, ChevronRight, House, MapPin, Plus } from 'lucide-vue-next';
import { labelKind, useAddressStore } from '@/stores/address/addressStore';
import { displayPhone } from '@/utils/phone';

const ICONS = { home: House, office: Briefcase, other: MapPin }

// The buyer's delivery addresses as cards: default first, then newest. A card opens its detail page,
// or with `picker` (cart) emits "pick" to use that address for this order.
export default {
    name: 'AddressList',
    components: { ChevronRight, MapPin, Plus },
    props: { picker: { type: Boolean, default: false } },
    emits: ['pick'],

    computed: {
        store() {
            return useAddressStore()
        },
    },

    methods: {
        displayPhone,
        icon(a) {
            return ICONS[labelKind(a.label)]
        },
        title(a) {
            const kind = labelKind(a.label)
            return kind === 'other' ? a.label || this.$t('delivery_address_page.card_title') : this.$t(`delivery_address_page.label_${kind}`)
        },
        open(a) {
            if (this.picker) this.$emit('pick', a)
            else this.$router.push(`/account/address/${a.id}`)
        },
    },

    async mounted() {
        // The cart's picker keeps the loaded list: a fetch would reset the address picked for this order
        if (this.picker && this.store.loaded) return
        try {
            await this.store.fetch()
        } catch (e) {
            console.error('AddressList - fetch -', e)
        }
    },
}
</script>

<template>
    <div class="address-list">
        <q-skeleton v-if="!store.loaded" type="rect" height="96px" animation="pulse" class="card-skeleton" />

        <template v-else>
            <div v-if="!store.addresses.length" class="empty">
                <MapPin :size="28" class="empty-icon" />
                <div>{{ $t('delivery_address_page.empty_list') }}</div>
            </div>

            <button v-for="a in store.addresses" :key="a.id" class="card" @click="open(a)">
                <component :is="icon(a)" :size="20" class="card-icon" />
                <div class="card-body">
                    <div class="card-head">
                        <span class="card-title">{{ title(a) }}</span>
                        <span v-if="a.is_default" class="chip">{{ $t('delivery_address_page.chip_default') }}</span>
                    </div>
                    <div class="card-receiver">{{ a.receiver_name }} · {{ displayPhone(a.phone_number) }}</div>
                    <div class="card-address">{{ a.address }}</div>
                </div>
                <ChevronRight :size="18" class="card-arrow" />
            </button>

            <q-btn class="btn-add" no-caps outline @click="$router.push(picker ? '/account/address/new?from=cart' : '/account/address/new')">
                <Plus :size="16" />
                <span>{{ $t('delivery_address_page.button_add') }}</span>
            </q-btn>
        </template>
    </div>
</template>

<style scoped>
.address-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.card-skeleton {
    border-radius: 12px;
}

.empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 32px 16px;
    border: 1px dashed rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    color: var(--text-secondary);
    text-align: center;
}

.empty-icon {
    color: var(--color-accent, #f5A623);
}

.card {
    width: 100%;
    text-align: left;
    padding: 14px;
    background: var(--bg-surface);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    color: inherit;
    font: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 12px;
}

.card-icon {
    flex-shrink: 0;
    color: var(--color-accent, #f5A623);
}

.card-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.card-arrow {
    flex-shrink: 0;
    color: var(--text-secondary);
}

.card-head {
    display: flex;
    align-items: center;
    gap: 8px;
}

.card-title {
    font-weight: 700;
    font-size: 15px;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.chip {
    flex-shrink: 0;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    color: #121b2f;
    background: var(--color-accent, #f5A623);
}

.card-receiver {
    font-size: 13px;
    color: var(--text-secondary);
    overflow-wrap: anywhere;
}

.card-address {
    font-size: 14px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.btn-add {
    padding: 12px;
    color: var(--color-accent, #f5A623);
    font-weight: 600;
    border-radius: 12px;
}

.btn-add span {
    margin-left: 6px;
}
</style>
