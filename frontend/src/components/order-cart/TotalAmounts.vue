<script>
import { ScanBarcode, AlertCircle, Calendar } from 'lucide-vue-next';
import { mapGetters, mapState } from 'pinia';
import { useCartStore } from '@/stores/cart/cartStore.js';
import { useOrderStore } from '@/stores/order/orderStore.js';
import { useAuthStore } from '@/stores/auth/authStore.js';
import { useDeliveryStore } from '@/stores/delivery/deliveryStore.js';
import apiPayments from '@/apis/payments/apiPayments.js';

export default {
    components: {
        ScanBarcode, AlertCircle, Calendar
    },

    data() {
        return {
            submitting: false,
            deliveryDate: null,
            deliveryTime: null,
        }
    },

    computed: {
        ...mapGetters(useCartStore, ['subtotalText', 'subtotal', 'maxPreorderDay']),
        ...mapState(useCartStore, ['cartItems', 'note', 'cart']),

        deliveryStore() {
            return useDeliveryStore()
        },
        deliveryFeeText() {
            return this.deliveryStore.deliveryFeeText
        },
        deliveryFee() {
            return this.deliveryStore.deliveryFee
        },
        quotationLoading() {
            return this.deliveryStore.quotationLoading
        },
        totalAmount() {
            return this.subtotal + this.deliveryFee
        },
        totalAmountText() {
            return new Intl.NumberFormat('vi-VN').format(this.totalAmount) + ' ₫'
        },
        isPreorder() {
            return this.maxPreorderDay > 0
        },
        deliveryAppointment() {
            if (!this.deliveryDate || !this.deliveryTime) return null
            return `${this.deliveryDate} ${this.deliveryTime}`
        },
        minAppointmentDatetime() {
            const d = new Date()
            d.setDate(d.getDate() + this.maxPreorderDay)
            return d
        },
        minAppointmentDate() {
            return this.minAppointmentDatetime.toISOString().slice(0, 10).replace(/-/g, '/')
        },
        validationIssues() {
            const auth = useAuthStore()
            const issues = []
            if (!auth.user?.phone) issues.push({ msg: this.$t('cart_page.validation.missing_phone'), route: '/account/profile' })
            if (!auth.inputAddress) issues.push({ msg: this.$t('cart_page.validation.missing_address'), route: '/account/address' })
            if (this.isPreorder && !this.deliveryAppointment) issues.push({ msg: this.$t('cart_page.validation.missing_appointment'), route: null })
            return issues
        },
        canPlaceOrder() {
            return this.cartItems.length > 0 && !this.submitting && !this.quotationLoading && this.validationIssues.length === 0
        },
        appointmentDateOptions() {
            return (dateStr) => dateStr >= this.minAppointmentDate
        },
        appointmentTimeOptions() {
            return (hr, min) => {
                if (!this.deliveryDate) return false
                if (this.deliveryDate.replace(/\//g, '-') > this.minAppointmentDate.replace(/\//g, '-')) return true
                const minHr = this.minAppointmentDatetime.getHours()
                const minMin = this.minAppointmentDatetime.getMinutes()
                if (min === null) return hr >= minHr
                if (hr > minHr) return true
                if (hr === minHr) return min >= minMin
                return false
            }
        },
    },

    watch: {
        validationIssues() {
            this.$nextTick(this._updateHeight)
        },
        deliveryDate() {
            this.deliveryTime = null
        },
    },

    methods: {
        _updateHeight() {
            const h = this.$refs?.totalAmountsRef?.offsetHeight || 0
            document.documentElement.style.setProperty('--total-amount-height', `${h}px`)
        },
        async onPlaceOrder() {
            if (this.submitting || this.validationIssues.length > 0) return
            this.submitting = true
            try {
                const authStore = useAuthStore()
                const address = authStore.inputAddress || authStore.user?.address || ''
                const lat = authStore.inputLat || null
                const lon = authStore.inputLon || null

                const deliveryOpts = {}
                if (lat != null) deliveryOpts.delivery_lat = lat
                if (lon != null) deliveryOpts.delivery_lon = lon
                if (this.deliveryFee) deliveryOpts.delivery_fee = this.deliveryFee
                if (this.deliveryStore.quotation?.quotation_id) {
                    deliveryOpts.quotation_id = this.deliveryStore.quotation.quotation_id
                }

                const orderStore = useOrderStore()
                const appt = this.isPreorder && this.deliveryDate && this.deliveryTime
                    ? new Date(`${this.deliveryDate.replace(/\//g, '-')}T${this.deliveryTime}:00`).toISOString()
                    : null
                const order = await orderStore.placeOrder('delivery', address, this.note || null, deliveryOpts, appt)
                if (order) {
                    const cartStore = useCartStore()
                    cartStore.$reset()
                    this.deliveryStore.reset()

                    // Open VNPay payment in new tab
                    try {
                        const payRes = await apiPayments.createVnpayPayment(order.id)
                        if (payRes?.data?.payment_url) {
                            // window.open(payRes.data.payment_url, '_blank')
                            window.location.href = payRes.data.payment_url
                        }
                    } catch (payErr) {
                        console.error('VNPay payment URL failed:', payErr)
                    }

                    this.$router.push({ name: 'order-confirmation', params: { orderId: order.id } })
                }
            } catch (e) {
                console.error(e)
                if (e.detail?.delivery_fee != null) {
                    // Server re-quoted a different fee: show it, buyer places the order again
                    this.deliveryStore.quotation = {
                        ...this.deliveryStore.quotation,
                        total_fee: e.detail.delivery_fee,
                        quotation_id: e.detail.quotation_id,
                    }
                    this.$q.notify({
                        type: 'warning',
                        message: this.$t('cart_page.delivery_fee_changed', { fee: this.deliveryFeeText }),
                        position: 'top'
                    })
                    return
                }
                const cartStore = useCartStore()
                await cartStore.refreshCart()
                this.$q.notify({
                    type: 'negative',
                    message: 'Failed to place order. Please try again.',
                    position: 'top'
                })
            } finally {
                this.submitting = false
            }
        }
    },

    mounted() {
        this._updateHeight()

        // Fetch delivery quotation if cart has items
        if (this.cart && this.cartItems.length > 0) {
            const authStore = useAuthStore()
            const lat = authStore.inputLat
            const lon = authStore.inputLon
            const sellerId = this.cart?.seller_id
            const address = authStore.inputAddress
            if (sellerId && lat && lon && address) {
                this.deliveryStore.getQuotation(sellerId, lat, lon, address)
            }
        }
    }
}
</script>

<template>
    <div ref='totalAmountsRef' class="container">
        <div class="subtotal-section">
            <div class="title sub-color">
                {{ $t('cart_page.section_total_amount.title_subtotal')  }}
            </div>
            <div class="price-text">
                {{ subtotalText }}
            </div>
        </div>

        <div class="subtotal-section">
            <div class="title sub-color">
                {{ $t('cart_page.section_total_amount.title_estimated_delivery_fee')  }}
            </div>
            <div class="price-text sub-color">
                <q-spinner-dots v-if="quotationLoading" color="amber" size="16px" />
                <span v-else>{{ deliveryFeeText }}</span>
            </div>
        </div>

        <div class="dashed-line" />

        <div class="subtotal-section">
            <div class="title-total">
                {{ $t('cart_page.section_total_amount.title_total_amount')  }}
            </div>
            <div class="price-text">
                {{ totalAmountText }}
            </div>
        </div>

        <div v-if="isPreorder" class="appointment-section">
            <div class="appointment-label">
                <Calendar :size="14" />
                <span>{{ $t('cart_page.preorder.label_delivery_date') }} <span class="required">*</span></span>
            </div>
            <div class="appointment-inputs">
                <q-input
                    v-model="deliveryDate"
                    dense readonly
                    :placeholder="$t('cart_page.preorder.placeholder_date')"
                    class="appointment-input"
                >
                    <template #append>
                        <q-icon name="event" class="cursor-pointer">
                            <q-popup-proxy transition-show="scale" transition-hide="scale">
                                <q-date
                                    v-model="deliveryDate"
                                    :options="appointmentDateOptions"
                                    minimal dark color="amber"
                                >
                                    <div class="row items-center justify-end">
                                        <q-btn v-close-popup flat no-caps :label="$t('cart_page.preorder.close')" color="amber" />
                                    </div>
                                </q-date>
                            </q-popup-proxy>
                        </q-icon>
                    </template>
                </q-input>
                <q-input
                    v-model="deliveryTime"
                    dense readonly
                    :placeholder="$t('cart_page.preorder.placeholder_time')"
                    :disable="!deliveryDate"
                    class="appointment-input"
                >
                    <template #append>
                        <q-icon name="access_time" class="cursor-pointer">
                            <q-popup-proxy transition-show="scale" transition-hide="scale">
                                <q-time
                                    v-model="deliveryTime"
                                    :options="appointmentTimeOptions"
                                    format24h dark color="amber"
                                >
                                    <div class="row items-center justify-end">
                                        <q-btn v-close-popup flat no-caps :label="$t('cart_page.preorder.close')" color="amber" />
                                    </div>
                                </q-time>
                            </q-popup-proxy>
                        </q-icon>
                    </template>
                </q-input>
            </div>
        </div>

        <div v-if="validationIssues.length > 0" class="validation-card">
            <AlertCircle class="validation-icon" :size="16" />
            <div class="validation-messages">
                <div v-for="issue in validationIssues" :key="issue.msg" class="validation-item">
                    {{ issue.msg }}
                    <router-link v-if="issue.route" :to="issue.route" class="validation-link">{{ $t('cart_page.validation.fix') }}</router-link>
                </div>
            </div>
        </div>

        <div class="button-checkout">
            <q-btn class="button" dense no-caps :loading="submitting" :disable="!canPlaceOrder" @click="onPlaceOrder">
                <ScanBarcode class="icon" /> Place Order · {{ totalAmountText }}
            </q-btn>
        </div>
    </div>
</template>

<style lang="scss" scoped>

.container {
    width: 100%;
    padding: 20px 15px;
    font-family: $sariko-font-family-secondary;
    background-color: var(--bg-surface);
    border-top-left-radius: 1.5rem;
    border-top-right-radius: 1.5rem;
}
.subtotal-section {
    display: flex;
    justify-content: space-between;
    margin-bottom: 15px;
    font-weight: 600;
}

.title {
    font-size: 14px;
    font-weight: 400;
}

.sub-color {
    color: rgb(255, 255, 255, 0.5)
}

.dashed-line {
    height: 1px;
    background: repeating-linear-gradient(
        to right,
        #454545 0px,
        #454545 10px,
        transparent 2px,
        transparent 15px
    );
    margin-top: 30px;
    margin-bottom: 15px;
}

.validation-card {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    background: rgba(248, 113, 113, 0.1);
    border: 1px solid rgba(248, 113, 113, 0.3);
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 12px;
}

.validation-icon {
    color: #f87171;
    flex-shrink: 0;
    margin-top: 2px;
}

.validation-messages {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex: 1;
}

.validation-item {
    font-size: 13px;
    color: #f87171;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.validation-link {
    font-size: 12px;
    font-weight: 600;
    color: $accent;
    text-decoration: none;
    flex-shrink: 0;
    margin-left: 8px;
}

.appointment-section {
    background: rgba(245, 166, 35, 0.08);
    border: 1px solid rgba(245, 166, 35, 0.25);
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 12px;
}

.appointment-inputs {
    display: flex;
    gap: 8px;

    .appointment-input {
        flex: 1;
    }
}

.appointment-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    margin-bottom: 8px;
}

.required {
    color: #f87171;
}

.appointment-input {
    color: var(--text-primary);

    :deep(.q-field__native),
    :deep(.q-field__input),
    :deep(input::placeholder) {
        color: rgba(255, 255, 255, 0.6) !important;
    }

    :deep(.q-field__control) {
        color: white;
    }

    :deep(.q-icon) {
        color: rgba(255, 255, 255, 0.6);
    }
}

.button {
    width: 100%;
    background-color: $accent;
    color: var(--bg-main);
    padding: 12px 0px;
    border-radius: 2rem;
    font-weight: 600;
    font-size: 18px;
    box-shadow: var(--cta-shadow);
}
.icon {
    margin-right: 12px;
}
</style>
