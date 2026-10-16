<script>
import JoinStepWelcome from '@/components/join/JoinStepWelcome.vue'
import JoinStepAbout from '@/components/join/JoinStepAbout.vue'
import JoinStepPlan from '@/components/join/JoinStepPlan.vue'
import JoinStepStore from '@/components/join/JoinStepStore.vue'
import JoinStepMenu from '@/components/join/JoinStepMenu.vue'
import JoinStepDocuments from '@/components/join/JoinStepDocuments.vue'
import JoinStepPayout from '@/components/join/JoinStepPayout.vue'
import JoinStepReview from '@/components/join/JoinStepReview.vue'
import { useJoinStore, STEP_COUNT } from '@/stores/join/joinStore'

// Plan comes before Menu: the plan sets how many dishes and categories are allowed.
const STEPS = [
    { key: 'welcome', comp: 'JoinStepWelcome' },
    { key: 'about', comp: 'JoinStepAbout' },
    { key: 'plan', comp: 'JoinStepPlan' },
    { key: 'store', comp: 'JoinStepStore' },
    { key: 'menu', comp: 'JoinStepMenu' },
    { key: 'documents', comp: 'JoinStepDocuments' },
    { key: 'payout', comp: 'JoinStepPayout' },
    { key: 'review', comp: 'JoinStepReview' },
]

export default {
    components: {
        JoinStepWelcome, JoinStepAbout, JoinStepPlan, JoinStepStore,
        JoinStepMenu, JoinStepDocuments, JoinStepPayout, JoinStepReview,
    },

    data() {
        return { steps: STEPS.map((s, i) => ({ ...s, n: i + 1 })), last: STEP_COUNT }
    },

    computed: {
        store() {
            return useJoinStore()
        },
        // Desktop: horizontal stepper (Menu as a table). Phone: vertical stepper (Menu as cards).
        wide() {
            return this.$q.screen.gt.sm
        },
    },

    methods: {
        onNext() {
            if (this.store.next()) this.scrollTop()
            else this.$nextTick(() => this.$el.querySelector('.q-field--error, .join-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
        },
        onBack() {
            this.store.back()
            this.scrollTop()
        },
        scrollTop() {
            this.$nextTick(() => this.$el.scrollIntoView({ behavior: 'smooth', block: 'start' }))
        },
    },
}
</script>

<template>
    <q-stepper
        v-model="store.step"
        :vertical="!wide"
        :alternative-labels="wide"
        dark flat animated
        active-color="amber" done-color="amber" inactive-color="grey-6"
        class="join-stepper"
    >
        <q-step
            v-for="s in steps"
            :key="s.n"
            :name="s.n"
            :title="$t(`join_page.step_${s.key}`)"
            :done="store.step > s.n"
        >
            <component :is="s.comp" />

            <q-stepper-navigation class="nav">
                <q-btn
                    v-if="s.n > 1"
                    flat no-caps
                    class="btn-back"
                    :disable="store.submitting"
                    :label="$t('join_page.button_back')"
                    @click="onBack"
                />
                <q-btn
                    v-if="s.n < last"
                    unelevated no-caps
                    class="btn-next"
                    :label="$t('join_page.button_continue')"
                    @click="onNext"
                />
            </q-stepper-navigation>
        </q-step>
    </q-stepper>
</template>

<style lang="scss" scoped>
.join-stepper {
    background: transparent;
}

.nav {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding-top: 16px;
}

.btn-back {
    color: rgba(255, 255, 255, 0.75);
}

.btn-next {
    padding: 8px 22px;
    background: #f5a623;
    color: #121b2f;
    font-weight: 700;
    border-radius: 12px;
}
</style>
