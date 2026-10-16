<script>
import { Trash2 } from 'lucide-vue-next'
import JoinDishPhoto from '@/components/join/JoinDishPhoto.vue'
import { useJoinStore } from '@/stores/join/joinStore'

// Desktop: one row per dish, like the Excel menu sellers know.
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
    <div class="table-wrap">
        <table class="menu-table">
            <thead>
                <tr>
                    <th class="col-n">#</th>
                    <th>{{ $t('join_page.label_category') }}</th>
                    <th>{{ $t('join_page.label_dish_name') }}</th>
                    <th>{{ $t('join_page.label_dish_description') }}</th>
                    <th class="col-price">{{ $t('join_page.label_price') }}</th>
                    <th class="col-unit">{{ $t('join_page.label_unit') }}</th>
                    <th class="col-avail">{{ $t('join_page.label_preorder') }}</th>
                    <th class="col-photo">{{ $t('join_page.label_photo') }}</th>
                    <th class="col-del"></th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="(dish, i) in store.menu" :key="dish.key">
                    <td class="col-n">{{ i + 1 }}</td>
                    <td>
                        <q-input v-model="dish.category" dark outlined dense color="amber" list="join-categories" :error="!!err(dish.key, 'category')" :error-message="err(dish.key, 'category')" maxlength="100" />
                    </td>
                    <td>
                        <q-input v-model="dish.name" dark outlined dense color="amber" :error="!!err(dish.key, 'name')" :error-message="err(dish.key, 'name')" maxlength="100" />
                    </td>
                    <td>
                        <q-input v-model="dish.description" dark outlined dense color="amber" autogrow maxlength="300" />
                    </td>
                    <td class="col-price">
                        <q-input v-model.number="dish.price" dark outlined dense color="amber" type="number" min="1000" step="1000" :hint="vnd(dish.price)" :error="!!err(dish.key, 'price')" :error-message="err(dish.key, 'price')" />
                    </td>
                    <td class="col-unit">
                        <q-input v-model="dish.unit_label" dark outlined dense color="amber" :placeholder="$t('join_page.placeholder_unit')" maxlength="30" />
                    </td>
                    <td class="col-avail">
                        <div class="avail">
                            <q-toggle v-model="dish.preorder" dark dense color="amber" />
                            <q-input v-if="dish.preorder" v-model.number="dish.preorder_day" dark outlined dense color="amber" type="number" min="1" :max="store.settings.max_preorder_days" :suffix="$t('join_page.suffix_days')" :error="!!err(dish.key, 'preorder_day')" :error-message="err(dish.key, 'preorder_day')" class="days" />
                            <span v-else class="join-hint">{{ $t('join_page.same_day') }}</span>
                        </div>
                    </td>
                    <td class="col-photo">
                        <JoinDishPhoto :dish-key="dish.key" />
                    </td>
                    <td class="col-del">
                        <q-btn flat round dense :aria-label="$t('join_page.menu_remove_dish')" @click="store.removeDish(dish.key)">
                            <Trash2 :size="16" />
                        </q-btn>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<style lang="scss" scoped>
.table-wrap {
    overflow-x: auto;
}

.menu-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

th {
    text-align: left;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.7);
    padding: 6px 4px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.15);
}

td {
    vertical-align: top;
    padding: 8px 4px 0;
}

.col-n {
    width: 28px;
    padding-top: 16px;
    color: rgba(255, 255, 255, 0.5);
}

.col-price {
    width: 130px;
}

.col-unit {
    width: 90px;
}

.col-avail {
    width: 140px;
}

.col-photo {
    width: 64px;
}

.col-del {
    width: 36px;
    padding-top: 12px;
}

.avail {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    padding-top: 8px;
}

.days {
    width: 90px;
    margin-top: -8px;
}
</style>
