<script>
import { useJoinStore } from '@/stores/join/joinStore'

export default {
    computed: {
        store() {
            return useJoinStore()
        },
        form() {
            return this.store.form
        },
        errors() {
            return this.store.visibleErrors(4)
        },
    },

    methods: {
        err(field) {
            return this.errors[field] ? this.$t(this.errors[field], this.store.limits) : ''
        },
    },
}
</script>

<template>
    <div class="join-step">
        <q-input v-model="form.store_name" dark outlined dense color="amber" :label="$t('join_page.label_store_name')" :error="!!err('store_name')" :error-message="err('store_name')" maxlength="300" />
        <q-input v-model="form.store_description" dark outlined dense color="amber" autogrow type="textarea" :label="$t('join_page.label_store_description')" :hint="$t('join_page.hint_store_description')" maxlength="1000" counter />

        <q-input v-model="form.pickup_address" dark outlined dense color="amber" :label="$t('join_page.label_pickup_address')" :hint="$t('join_page.hint_pickup_address')" :error="!!err('pickup_address')" :error-message="err('pickup_address')" maxlength="300" />
        <q-input v-model="form.maps_link" dark outlined dense color="amber" type="url" :label="$t('join_page.label_maps_link')" :hint="$t('join_page.hint_maps_link')" :error="!!err('maps_link')" :error-message="err('maps_link')" maxlength="300" />

        <div class="join-grid">
            <q-input v-model="form.opening_time" dark outlined dense color="amber" stack-label type="time" :label="$t('join_page.label_opening_time')" />
            <q-input v-model="form.closing_time" dark outlined dense color="amber" stack-label type="time" :label="$t('join_page.label_closing_time')" :error="!!err('closing_time')" :error-message="err('closing_time')" />
        </div>
    </div>
</template>
