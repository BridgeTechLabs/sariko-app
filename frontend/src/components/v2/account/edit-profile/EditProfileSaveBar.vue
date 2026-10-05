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
        ...mapState(useAccountV2Store, ['isProfileFormDirty', 'isProfileFormValid', 'avatarUploading']),
    },

    methods: {
        ...mapActions(useAccountV2Store, ['saveProfileForm']),

        async onClickedSave() {
            if (this.saving) return
            // Reveals name/phone errors in EditProfileForm
            useAccountV2Store().profileFormSubmitted = true
            if (!this.isProfileFormValid) return

            this.saving = true
            try {
                await this.saveProfileForm()
                this.$q.notify({
                    classes: 'notify-v2-success',
                    icon: 'fa-solid fa-check',
                    message: this.$t('account_v2.edit_profile_saved'),
                    position: 'bottom',
                    timeout: 2000,
                })
                this.$router.push({ name: 'account-v2' })
            } catch (error) {
                console.error(`EditProfileSaveBar - onClickedSave - ${error}`)
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
            :disabled="!isProfileFormDirty || avatarUploading || saving"
            @click="onClickedSave"
        >
            {{ $t('account_v2.edit_profile_save') }}
        </BaseButton>
    </div>
</template>

<style scoped>
/* Figma shadow/floating */
.save-bar {
    position: sticky;
    bottom: 0;
    padding: var(--space-16) var(--space-24) max(var(--space-32), calc(env(safe-area-inset-bottom, 0px) + var(--space-16)));
    background: var(--card);
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
    box-shadow:
        0 2px 4px color-mix(in srgb, var(--brand-navy) 8%, transparent),
        0 16px 40px -8px color-mix(in srgb, var(--brand-navy) 16%, transparent);
}

.save-btn {
    width: 100%;
}
</style>
