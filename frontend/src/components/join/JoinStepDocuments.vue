<script>
import { FileText, X } from 'lucide-vue-next'
import { useJoinStore, DOCUMENT_KINDS } from '@/stores/join/joinStore'

export default {
    components: { FileText, X },

    data() {
        return { kinds: DOCUMENT_KINDS, loading: null }
    },

    computed: {
        store() {
            return useJoinStore()
        },
        error() {
            const key = this.store.visibleErrors(6).id_document
            return key ? this.$t(key, this.store.limits) : ''
        },
    },

    methods: {
        async onPick(kind, event) {
            const files = [...(event.target.files || [])]
            event.target.value = ''
            this.loading = kind
            try {
                for (const file of files) await this.store.addDocument(kind, file)
            } catch (key) {
                this.$q.notify({ type: 'negative', message: this.$t(typeof key === 'string' ? key : 'join_page.error_file_type', this.store.limits), position: 'bottom' })
            } finally {
                this.loading = null
            }
        },
    },
}
</script>

<template>
    <div class="join-step">
        <div class="join-hint">{{ $t('join_page.documents_hint', store.limits) }}</div>

        <div v-for="kind in kinds" :key="kind" class="join-card doc">
            <div class="doc-head">
                <div>
                    <div class="doc-title">{{ $t(`join_page.doc_${kind}`) }}</div>
                    <div class="join-hint">{{ $t(`join_page.doc_${kind}_hint`) }}</div>
                </div>
                <label class="btn-pick" :class="{ disabled: store.documents[kind].length >= store.settings.max_files_per_kind }">
                    <input
                        type="file"
                        accept="image/jpeg,image/png,application/pdf"
                        :multiple="kind === 'id_document'"
                        class="hidden-input"
                        :disabled="store.documents[kind].length >= store.settings.max_files_per_kind || store.submitting"
                        @change="onPick(kind, $event)"
                    />
                    <q-spinner v-if="loading === kind" size="14px" />
                    <span v-else>{{ $t('join_page.documents_add') }}</span>
                </label>
            </div>

            <div v-for="(doc, i) in store.documents[kind]" :key="i" class="doc-file">
                <FileText :size="16" />
                <span class="doc-name">{{ doc.name }}</span>
                <q-btn flat round dense size="sm" :disable="store.submitting" :aria-label="$t('join_page.documents_remove')" @click="store.removeDocument(kind, i)">
                    <X :size="14" />
                </q-btn>
            </div>

            <div v-if="kind === 'id_document' && error" class="join-error">{{ error }}</div>
        </div>
    </div>
</template>

<style lang="scss" scoped>
.doc {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.doc-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
}

.doc-title {
    font-weight: 700;
    font-size: 14px;
}

.btn-pick {
    position: relative;
    flex-shrink: 0;
    padding: 6px 12px;
    border: 1px solid #f5a623;
    border-radius: 10px;
    color: #f5a623;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
}

.btn-pick.disabled {
    opacity: 0.4;
    cursor: default;
}

.doc-file {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
}

.doc-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.hidden-input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
}
</style>
