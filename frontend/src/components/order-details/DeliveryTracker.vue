<script>
import { Bike, Phone, ExternalLink, Loader, Package, MapPin, CircleCheck, ChefHat } from 'lucide-vue-next';
import { mapState } from 'pinia';
import { useDeliveryStore } from '@/stores/delivery/deliveryStore';
import { useOrderStore } from '@/stores/order/orderStore.js';
import { isScheduled } from '@/utils/orderStage';

const STEPS = [
    { key: 'PREPARING', icon: 'ChefHat' },
    { key: 'ASSIGNING_DRIVER', icon: 'Loader' },
    { key: 'ON_GOING', icon: 'Bike' },
    { key: 'PICKED_UP', icon: 'Package' },
    { key: 'COMPLETED', icon: 'CircleCheck' },
]

export default {
    components: { Bike, Phone, ExternalLink, Loader, Package, MapPin, CircleCheck, ChefHat },

    props: {
        orderStatus: { type: String, default: null },
    },

    computed: {
        ...mapState(useDeliveryStore, ['currentDelivery']),

        delivery() {
            return this.currentDelivery
        },
        currentStatus() {
            return this.delivery?.status || 'PREPARING'
        },
        isCancelled() {
            return ['CANCELLED', 'CANCELED', 'REJECTED', 'EXPIRED'].includes(this.currentStatus)
        },
        currentStepIndex() {
            const idx = STEPS.findIndex(s => s.key === this.currentStatus)
            return idx >= 0 ? idx : 0
        },
        steps() {
            const scheduled = isScheduled(useOrderStore().currentOrder)
            return STEPS.map((step, i) => ({
                ...step,
                label: this.$t(`delivery_tracker.status_${scheduled && i === 0 ? 'SCHEDULED' : step.key}`),
                active: i <= this.currentStepIndex,
                current: i === this.currentStepIndex,
            }))
        },
        hasDriver() {
            return !!this.delivery?.driver_name
        },
        hasTrackingUrl() {
            return !!this.delivery?.share_link || !!this.delivery?.tracking_url
        },
        trackingUrl() {
            return this.delivery?.tracking_url || this.delivery?.share_link
        },
    },

    methods: {
        callDriver() {
            if (this.delivery?.driver_phone) {
                window.open(`tel:${this.delivery.driver_phone}`, '_self')
            }
        },
        openTracking() {
            if (this.trackingUrl) {
                window.open(this.trackingUrl, '_blank')
            }
        },
    }
}
</script>

<template>
    <div v-if="delivery || orderStatus" class="delivery-tracker">

        <div class="tracker-title">{{ $t('delivery_tracker.title') }}</div>

        <!-- Cancelled state -->
        <div v-if="isCancelled" class="cancelled-notice">
            {{ $t('delivery_tracker.status_CANCELLED') }}
        </div>

        <!-- Status Timeline -->
        <div v-else class="timeline">
            <div
                v-for="(step, i) in steps"
                :key="step.key"
                class="timeline-step"
                :class="{ active: step.active, current: step.current }"
            >
                <div class="step-dot">
                    <component :is="step.icon" :size="14" />
                </div>
                <div v-if="i < steps.length - 1" class="step-line" :class="{ filled: steps[i + 1]?.active }" />
                <div class="step-label">{{ step.label }}</div>
            </div>
        </div>

        <!-- Driver Card -->
        <div v-if="hasDriver && !isCancelled && currentStatus !== 'COMPLETED'" class="driver-card">
            <div class="driver-avatar">
                <Bike :size="20" />
            </div>
            <div class="driver-info">
                <div class="driver-name">{{ delivery.driver_name }}</div>
                <div class="driver-plate">{{ delivery.driver_plate }}</div>
            </div>
            <button class="call-btn" @click="callDriver">
                <Phone :size="16" />
            </button>
        </div>

        <!-- Tracking Link -->
        <button v-if="hasTrackingUrl && !isCancelled && currentStatus !== 'COMPLETED'" class="tracking-btn" @click="openTracking">
            <MapPin :size="16" />
            {{ $t('delivery_tracker.track_rider') }}
            <ExternalLink :size="14" />
        </button>

    </div>
</template>

<style scoped>
.delivery-tracker {
    background: var(--bg-surface);
    border-radius: 16px;
    padding: 20px;
}

.tracker-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 20px;
}

/* Timeline */
.timeline {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 20px;
    position: relative;
}

.timeline-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    position: relative;
}

.step-dot {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1;
    transition: all 0.3s ease;
}

.timeline-step.active .step-dot {
    background: rgba(245, 166, 35, 0.2);
    color: var(--color-accent);
}

.timeline-step.current .step-dot {
    background: var(--color-accent);
    color: #121b2f;
    box-shadow: 0 0 12px rgba(245, 166, 35, 0.4);
    position: relative;
}

.timeline-step.current:not(:last-child) .step-dot::before {
    content: '';
    position: absolute;
    inset: -5px;
    border-radius: 50%;
    border: 2px solid transparent;
    border-top-color: var(--color-accent);
    border-right-color: rgba(245, 166, 35, 0.4);
    animation: spin-ring 1.2s linear infinite;
}

@keyframes spin-ring {
    to { transform: rotate(360deg); }
}

.step-line {
    position: absolute;
    top: 16px;
    left: calc(50% + 16px);
    right: calc(-50% + 16px);
    height: 2px;
    background: rgba(255, 255, 255, 0.1);
    z-index: 0;
}

.step-line.filled {
    background: var(--color-accent);
}

.step-label {
    margin-top: 8px;
    font-size: 10px;
    color: var(--text-muted);
    text-align: center;
    max-width: 70px;
    line-height: 1.3;
}

.timeline-step.active .step-label {
    color: var(--text-secondary);
}

.timeline-step.current .step-label {
    color: var(--color-accent);
    font-weight: 600;
}

/* Driver Card */
.driver-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    margin-bottom: 12px;
}

.driver-avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: rgba(245, 166, 35, 0.15);
    color: var(--color-accent);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.driver-info {
    flex: 1;
    min-width: 0;
}

.driver-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

.driver-plate {
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 2px;
}

.call-btn {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
}

.cancelled-notice {
    text-align: center;
    padding: 16px;
    color: #f87171;
    font-size: 14px;
    font-weight: 600;
    background: rgba(248, 113, 113, 0.1);
    border-radius: 10px;
    margin-bottom: 12px;
}

/* Tracking Button */
.tracking-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px;
    background: rgba(245, 166, 35, 0.1);
    border: 1px solid rgba(245, 166, 35, 0.3);
    border-radius: 12px;
    color: var(--color-accent);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
}
</style>
