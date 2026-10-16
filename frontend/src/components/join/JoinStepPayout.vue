<script>
import { useJoinStore, BANKS } from '@/stores/join/joinStore'

export default {
    data() {
        return { banks: BANKS }
    },

    computed: {
        store() {
            return useJoinStore()
        },
        form() {
            return this.store.form
        },
        errors() {
            return this.store.visibleErrors(7)
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
        <div class="join-hint">{{ $t('join_page.payout_hint') }}</div>
        <div class="join-grid">
            <q-select v-model="form.bank_name" dark outlined dense color="amber" :options="banks" :label="$t('join_page.label_bank_name')" :error="!!err('bank_name')" :error-message="err('bank_name')" />
            <q-input v-if="form.bank_name === 'Other'" v-model="form.bank_name_other" dark outlined dense color="amber" :label="$t('join_page.label_bank_name_other')" :error="!!err('bank_name_other')" :error-message="err('bank_name_other')" maxlength="300" />
            <q-input v-model="form.bank_account_number" dark outlined dense color="amber" inputmode="numeric" :label="$t('join_page.label_bank_account_number')" :error="!!err('bank_account_number')" :error-message="err('bank_account_number')" maxlength="30" />
        </div>
        <q-input v-model="form.bank_account_holder" dark outlined dense color="amber" :label="$t('join_page.label_bank_account_holder')" :hint="$t('join_page.hint_bank_account_holder')" :error="!!err('bank_account_holder')" :error-message="err('bank_account_holder')" maxlength="300" />
    </div>
</template>
