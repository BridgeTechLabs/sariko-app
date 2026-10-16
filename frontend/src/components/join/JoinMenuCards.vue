<script>
import { Trash2 } from 'lucide-vue-next'
import JoinDishPhoto from '@/components/join/JoinDishPhoto.vue'
import { useJoinStore } from '@/stores/join/joinStore'

// Phone: one card per dish, photo first so it can be taken with the camera.
export default {
    components: { Trash2, JoinDishPhoto },

    computed: {
        store() {
            return useJoinStore()
        },
    },

    methods: {
        err(key, field) {
            const e = this.store.dishErrors(key)[field]
            return e ? this.$t(e, this.store.limits) : ''
        },
        vnd(price) {
            const n = Number(price)
            return Number.isInteger(n) && n > 0 ? new Intl.NumberFormat('vi-VN').format(n) + ' ₫' : ''
        },
    },
}
</script>

<template>
    <div class="cards">
        <div v-for="(dish, i) in store.menu" :key="dish.key" class="join-card dish">
            <div class="dish-head">
                <span class="dish-n">{{ $t('join_page.menu_dish_n', { n: i + 1 }) }}</span>
                <q-btn flat round dense :aria-label="$t('join_page.menu_remove_dish')" @click="store.removeDish(dish.key)">
                    <Trash2 :size="16" />
                </q-btn>
            </div>

            <JoinDishPhoto :dish-key="dish.key" large />
            <div v-if="err(dish.key, 'photo') && !store.photos[dish.key]" class="join-error">{{ err(dish.key, 'photo') }}</div>

            <q-input v-model="dish.category" dark outlined dense color="amber" list="join-categories" :label="$t('join_page.label_category')" :error="!!err(dish.key, 'category')" :error-message="err(dish.key, 'category')" maxlength="100" />
            <q-input v-model="dish.name" dark outlined dense color="amber" :label="$t('join_page.label_dish_name')" :error="!!err(dish.key, 'name')" :error-message="err(dish.key, 'name')" maxlength="100" />
            <q-input v-model="dish.description" dark outlined dense color="amber" autogrow :label="$t('join_page.label_dish_description')" maxlength="300" />
            <div class="row-2">
                <q-input v-model.number="dish.price" dark outlined dense color="amber" type="number" inputmode="numeric" min="1000" step="1000" :label="$t('join_page.label_price')" :hint="vnd(dish.price)" :error="!!err(dish.key, 'price')" :error-message="err(dish.key, 'price')" />
                <q-input v-model="dish.unit_label" dark outlined dense color="amber" :label="$t('join_page.label_unit')" :placeholder="$t('join_page.placeholder_unit')" maxlength="30" />
            </div>
            <div class="avail">
                <q-toggle v-model="dish.preorder" dark dense color="amber" :label="$t('join_page.label_preorder')" />
                <q-input v-if="dish.preorder" v-model.number="dish.preorder_day" dark outlined dense color="amber" type="number" min="1" :max="store.settings.max_preorder_days" :suffix="$t('join_page.suffix_days')" :error="!!err(dish.key, 'preorder_day')" :error-message="err(dish.key, 'preorder_day')" class="days" />
                <span v-else class="join-hint">{{ $t('join_page.same_day') }}</span>
            </div>
        </div>
    </div>
</template>

<style lang="scss" scoped>
.cards {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.dish {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.dish-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.dish-n {
    font-weight: 700;
    font-size: 14px;
}

.row-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}

.avail {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 40px;
}

.days {
    width: 110px;
}
</style>
