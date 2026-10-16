<script>
import { Plus } from 'lucide-vue-next'
import JoinMenuTable from '@/components/join/JoinMenuTable.vue'
import JoinMenuCards from '@/components/join/JoinMenuCards.vue'
import { useJoinStore } from '@/stores/join/joinStore'

export default {
    components: { Plus, JoinMenuTable, JoinMenuCards },

    computed: {
        store() {
            return useJoinStore()
        },
        error() {
            const key = this.store.visibleErrors(5).menu
            return key ? this.$t(key, this.store.limits) : ''
        },
        categoryLimit() {
            return this.store.tier.maxCategories ?? '∞'
        },
    },

    mounted() {
        if (!this.store.menu.length) this.store.addDish()
    },
}
</script>

<template>
    <div class="join-step">
        <div class="join-hint">{{ $t('join_page.menu_hint') }}</div>
        <div class="join-hint">{{ $t('join_page.menu_photo_hint') }}</div>

        <div class="counter">
            {{ $t('join_page.menu_counter', {
                items: store.menu.length, maxItems: store.maxItems,
                categories: store.categories.length, maxCategories: categoryLimit,
                plan: $t(`join_page.tier_${store.tier.id}`),
            }) }}
        </div>

        <!-- Suggestions for the category inputs -->
        <datalist id="join-categories">
            <option v-for="c in store.categories" :key="c" :value="c" />
        </datalist>

        <JoinMenuTable v-if="$q.screen.gt.sm" />
        <JoinMenuCards v-else />

        <div v-if="error" class="join-error">{{ error }}</div>

        <q-btn
            outline no-caps
            class="btn-add"
            :disable="store.menu.length >= store.maxItems"
            @click="store.addDish()"
        >
            <Plus :size="16" />&nbsp;{{ $t('join_page.menu_add_dish') }}
        </q-btn>
    </div>
</template>

<style lang="scss" scoped>
.counter {
    font-size: 13px;
    font-weight: 600;
    color: #f5a623;
}

.btn-add {
    align-self: flex-start;
    color: #f5a623;
    border-radius: 12px;
}
</style>
