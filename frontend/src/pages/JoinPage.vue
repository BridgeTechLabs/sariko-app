<script>
import LayoutJoin from '@/layouts/join/LayoutJoin.vue'
import JoinHeader from '@/components/join/JoinHeader.vue'
import JoinMobileTip from '@/components/join/JoinMobileTip.vue'
import JoinWizard from '@/components/join/JoinWizard.vue'
import JoinDone from '@/components/join/JoinDone.vue'
import { useJoinStore } from '@/stores/join/joinStore'

export default {
    name: 'JoinPage',
    components: { LayoutJoin, JoinHeader, JoinMobileTip, JoinWizard, JoinDone },

    computed: {
        store() {
            return useJoinStore()
        },
    },

    mounted() {
        this.store.loadSettings()
        this.store.loadDraft()
        // Keep typed text if the browser is closed half-way; files can't be kept.
        this.stopDraft = this.store.$subscribe(() => {
            if (!this.store.reference) this.store.saveDraft()
        })
    },

    beforeUnmount() {
        this.stopDraft?.()
    },
}
</script>

<template>
    <LayoutJoin>
        <template #header>
            <JoinHeader />
        </template>
        <template #tip>
            <JoinMobileTip v-if="!store.reference" />
        </template>
        <template #content>
            <JoinDone v-if="store.reference" />
            <JoinWizard v-else-if="store.settings" />
            <div v-else-if="store.settingsFailed" class="settings-failed">
                <div>{{ $t('join_page.error_settings') }}</div>
                <q-btn flat no-caps color="amber" :label="$t('join_page.button_reload')" @click="store.loadSettings()" />
            </div>
            <div v-else class="settings-loading"><q-spinner color="amber" size="32px" /></div>
        </template>
    </LayoutJoin>
</template>

<style scoped>
.settings-loading,
.settings-failed {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 48px 0;
    font-size: 14px;
    text-align: center;
}
</style>
