<script>
import { mapState, mapActions } from 'pinia';
import { useAccountV2Store } from '@/stores/v2/account/accountStore';
import BaseButton from '@/components/v2/shared/BaseButton.vue';

export default {
    components: { BaseButton },

    data() {
        return {
            saving: false,
        }
    },

    computed: {
        ...mapState(useAccountV2Store, ['isEditingAddress', 'isAddressFormReady', 'isAddressFormValid']),
    },

    methods: {
        ...mapActions(useAccountV2Store, ['saveAddressForm']),

        async onClickedSave() {
            if (this.saving) return
            // Reveals receiver/phone errors in AddressForm
            useAccountV2Store().addressFormSubmitted = true
            if (!this.isAddressFormValid) return

            this.saving = true
            try {
                await this.saveAddressForm()
                this.$q.notify({
                    classes: 'quasar-notify-positive',
                    message: `✔️ ${this.$t('common.toast_update_success')}`,
                    position: 'bottom',
                    timeout: 1500,
                })
                this.$router.push({ name: 'account-addresses-v2' })
            } catch (error) {
                console.error(`AddressFormSaveBar - onClickedSave - ${error}`)
                this.$q.notify({
                    classes: 'quasar-notify-negative',
                    message: this.$t('common.toast_update_failed'),
                    position: 'bottom',
                    timeout: 2000,
                })
            } finally {
                this.saving = false
            }
        },
    },
}
</script>

<template>
    <div class="save-bar">
        <BaseButton
            class="save-btn"
            :disabled="!isAddressFormReady || saving"
            @click="onClickedSave"
        >
            {{ isEditingAddress ? $t('account_v2.address_form_save_changes') : $t('account_v2.address_form_save') }}
        </BaseButton>
    </div>
</template>

<style scoped>
.save-bar {
    position: sticky;
    bottom: 0;
    padding: var(--space-16) var(--space-24) max(var(--space-32), calc(env(safe-area-inset-bottom, 0px) + var(--space-16)));
    background: var(--card);
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
}

.save-btn {
    width: 100%;
}
</style>
