<script>
import { useOrderStore } from '@/stores/order/orderStore.js';
import { useReviewStore } from '@/stores/review/reviewStore.js';

export default {
    data() {
        return {
            showUnratedDialog: false,
        }
    },

    computed: {
        reviewStore() {
            return useReviewStore()
        },
        orderId() {
            return this.$route.params.orderId
        },
        // Dishes left at 0 stars. Submitting is one-shot, so these can never be rated
        // from this order again — worth one confirmation before it becomes permanent.
        unratedCount() {
            const dishIds = new Set((useOrderStore().currentOrder?.order_items || [])
                .map(item => item.food_item_id).filter(Boolean))
            return [...dishIds].filter(
                id => !(this.reviewStore.itemDrafts[id]?.rating > 0)
            ).length
        }
    },

    methods: {
        onSubmitClick() {
            if (this.unratedCount > 0) {
                this.showUnratedDialog = true
                return
            }
            this.onSubmit()
        },

        onConfirmUnrated() {
            this.showUnratedDialog = false
            this.onSubmit()
        },

        async onSubmit() {
            try {
                const ok = await this.reviewStore.submitReview(this.orderId)
                if (!ok) {
                    this.$q.notify({ type: 'negative', message: this.$t('order_review.error_submit'), position: 'top' })
                    return
                }
                this.$q.notify({ type: 'positive', message: this.$t('order_review.success'), position: 'top' })
                this.reviewStore.resetDraft()
                // replace, not push: the review screen is spent — Back should return
                // to the order, not to a form that now 409s.
                this.$router.replace(`/orders/${this.orderId}`)
            } catch (e) {
                const message = e.status === 409
                    ? this.$t('order_review.error_already_reviewed')
                    : this.$t('order_review.error_submit')
                this.$q.notify({ type: 'negative', message, position: 'top' })
                if (e.status === 409) this.$router.replace(`/orders/${this.orderId}`)
            }
        }
    }
}
</script>

<template>
    <div>
        <q-btn
            class="btn-submit"
            dense
            no-caps
            :disable="!reviewStore.canSubmit"
            :loading="reviewStore.submitting"
            @click="onSubmitClick"
        >
            {{ $t('order_review.btn_submit') }}
        </q-btn>

        <q-dialog v-model="showUnratedDialog">
            <q-card class="unrated-dialog">
                <q-card-section>
                    <div class="dialog-title">{{ $t('order_review.dialog_unrated_title') }}</div>
                    <div class="dialog-text">
                        {{ $t('order_review.dialog_unrated_text', { count: unratedCount }) }}
                    </div>
                </q-card-section>
                <q-card-actions align="right">
                    <q-btn flat no-caps :label="$t('order_review.dialog_back')" v-close-popup />
                    <q-btn
                        flat
                        no-caps
                        color="amber"
                        :label="$t('order_review.dialog_submit_anyway')"
                        @click="onConfirmUnrated"
                    />
                </q-card-actions>
            </q-card>
        </q-dialog>
    </div>
</template>

<style scoped>
.btn-submit {
    width: 100%;
    background-color: var(--color-accent);
    color: #121b2f;
    padding: 14px 0;
    border-radius: 2rem;
    font-weight: 700;
    font-size: 16px;
}

.btn-submit:disabled {
    opacity: 0.4;
}

/* Mirrors the cancel dialog on the order detail screen. */
.unrated-dialog {
    background-color: #1f2940;
    border-radius: 16px;
    min-width: 280px;
}

.dialog-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 8px;
}

.dialog-text {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.5);
}
</style>
