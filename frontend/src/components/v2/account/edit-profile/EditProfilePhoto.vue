<script>
import { mapState, mapActions } from 'pinia';
import { useAccountV2Store } from '@/stores/v2/account/accountStore';
import BaseAvatar from '@/components/v2/shared/BaseAvatar.vue';
import BaseIcon from '@/components/v2/shared/BaseIcon.vue';

export default {
    components: { BaseAvatar, BaseIcon },

    computed: {
        ...mapState(useAccountV2Store, ['profileForm', 'avatarPreview', 'avatarUploading', 'avatarErrorKey']),

        // Follows the name being typed, like the Account header
        initials() {
            return this.profileForm.name
                .split(' ')
                .filter(Boolean)
                .map(word => word[0])
                .join('')
                .slice(0, 2)
                .toUpperCase()
        },
    },

    methods: {
        ...mapActions(useAccountV2Store, ['uploadProfileAvatar']),

        onClickedPhoto() {
            if (this.avatarUploading) return
            this.$refs.fileInput.click()
        },

        async onFileSelected(event) {
            const file = event.target.files[0]
            // Reset so picking the same file again still fires change
            event.target.value = ''
            if (!file) return

            try {
                await this.uploadProfileAvatar(file)
            } catch (error) {
                console.error(`EditProfilePhoto - onFileSelected - ${error}`)
                this.$q.notify({
                    classes: 'quasar-notify-negative',
                    message: this.$t('common.toast_update_failed'),
                    position: 'bottom',
                    timeout: 2000,
                })
            }
        },
    },
}
</script>

<template>
    <div class="edit-profile-photo">
        <button
            class="avatar-wrap"
            type="button"
            :aria-label="$t('account_v2.edit_profile_photo_hint')"
            @click="onClickedPhoto"
        >
            <BaseAvatar
                :class="{ uploading: avatarUploading }"
                :src="avatarPreview || profileForm.avatarUrl || null"
                :initials="initials"
                :size="96"
            />
            <span class="camera">
                <BaseIcon name="camera" :size="16" />
            </span>
        </button>

        <p v-if="avatarErrorKey" class="caption error">{{ $t(avatarErrorKey) }}</p>
        <p v-else class="caption">{{ $t('account_v2.edit_profile_photo_hint') }}</p>

        <input
            ref="fileInput"
            class="file-input"
            type="file"
            accept="image/*"
            @change="onFileSelected"
        />
    </div>
</template>

<style scoped>
p {
    margin: 0;
}

.edit-profile-photo {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-8);
}

.avatar-wrap {
    position: relative;
    width: 96px;
    height: 96px;
    padding: 0;
    border: none;
    background: transparent;
    cursor: pointer;
}

.uploading {
    opacity: 0.6;
}

.camera {
    position: absolute;
    left: 64px;
    top: 64px;
    width: 32px;
    height: 32px;
    border: var(--border-strong) solid var(--background);
    border-radius: var(--radius-full);
    background: var(--primary);
    color: var(--primary-foreground);
    display: flex;
    align-items: center;
    justify-content: center;
}

.caption {
    font-size: var(--font-size-xs);
    line-height: var(--font-line-height-16);
    color: var(--text-secondary);
    text-align: center;
}

.caption.error {
    font-weight: var(--font-weight-semibold);
    color: var(--status-error);
}

.file-input {
    display: none;
}
</style>
