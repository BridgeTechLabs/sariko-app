<script>
import { Terminal, Zap, X } from 'lucide-vue-next';
import { apiClient } from '@/lib/axiosPolicy.js';

export default {
    components: { Terminal, Zap, X },

    data() {
        return {
            show: false,
            orderId: '',
            loading: false,
            log: [],
            orders: [],
        }
    },

    mounted() {
        window.addEventListener('keydown', this.onKeydown)
    },

    beforeUnmount() {
        window.removeEventListener('keydown', this.onKeydown)
    },

    methods: {
        onKeydown(e) {
            if (e.ctrlKey && e.shiftKey && e.key === 'Q') {
                e.preventDefault()
                this.show = !this.show
                if (this.show) this.loadOrders()
            }
        },

        // Own buyer orders (incl. unpaid) + own shop's orders (paid only). _silent: a buyer gets 403/404 on the seller list.
        async loadOrders() {
            const [buyer, seller] = await Promise.allSettled([
                apiClient.get('/v1/orders', { _silent: true }),
                apiClient.get('/v1/sellers/me/orders', { _silent: true }),
            ])
            const all = [
                ...(buyer.value?.data?.orders || []),
                ...(seller.value?.data?.orders || []),
            ]
            const byId = new Map(all.map((o) => [o.id, o]))
            this.orders = [...byId.values()].sort((a, b) => b.created_at.localeCompare(a.created_at))
        },

        orderLabel(o) {
            const time = new Date(o.created_at).toLocaleString('en-GB', { hour12: false, day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
            return `#${o.id.slice(0, 8)} · ${o.status} · ${o.payment_status} · ${o.total_amount}₫ · ${time}`
        },

        addLog(msg, type = 'info') {
            const ts = new Date().toLocaleTimeString('en-GB', { hour12: false })
            this.log.unshift({ ts, msg, type })
            if (this.log.length > 50) this.log.pop()
        },

        // action: 'force-pay' → paid, 'force-unpay' → pending
        async forcePaymentPaid(action = 'force-pay') {
            if (!this.orderId.trim() || this.loading) return
            const id = this.orderId.trim()
            this.loading = true
            this.addLog(`> ${action} ${id}`)
            try {
                const res = await apiClient.patch(`/v1/dev/orders/${id}/${action}`)
                if (res.data?.success) {
                    this.addLog(`✔ order ${id} → payment_status=${action === 'force-pay' ? 'paid' : 'pending'}`, 'success')
                } else {
                    this.addLog(`✘ ${JSON.stringify(res.data)}`, 'error')
                }
            } catch (e) {
                const detail = e.response?.data?.detail || e.message
                this.addLog(`✘ ${detail}`, 'error')
            } finally {
                this.loading = false
                this.loadOrders()
            }
        },

        async forceOrderStatus(status) {
            if (!this.orderId.trim() || this.loading) return
            const id = this.orderId.trim()
            this.loading = true
            this.addLog(`> force-status ${id} → ${status}`)
            try {
                const res = await apiClient.patch(`/v1/dev/orders/${id}/force-status`, { status })
                if (res.data?.success) {
                    this.addLog(`✔ order ${id} → status=${status}`, 'success')
                } else {
                    this.addLog(`✘ ${JSON.stringify(res.data)}`, 'error')
                }
            } catch (e) {
                const detail = e.response?.data?.detail || e.message
                this.addLog(`✘ ${detail}`, 'error')
            } finally {
                this.loading = false
                this.loadOrders()
            }
        },

        close() {
            this.show = false
        }
    }
}
</script>

<template>
    <teleport to="body">
        <transition name="panel-slide">
            <div v-if="show" class="hacker-overlay" @click.self="close">
                <div class="hacker-panel">
                    <!-- Header -->
                    <div class="panel-header">
                        <Terminal :size="16" />
                        <span class="header-title">SARIKO DEV PANEL</span>
                        <button class="close-btn" @click="close"><X :size="14" /></button>
                    </div>

                    <!-- Order picker -->
                    <div class="input-row picker-row">
                        <select v-model="orderId" class="order-input">
                            <option value="">{{ orders.length ? 'pick an order...' : 'no orders found' }}</option>
                            <option v-for="o in orders" :key="o.id" :value="o.id">{{ orderLabel(o) }}</option>
                        </select>
                        <button class="action-btn" :disabled="loading" @click="loadOrders">↻</button>
                    </div>

                    <!-- Order ID input -->
                    <div class="input-row">
                        <input
                            v-model="orderId"
                            class="order-input"
                            placeholder="paste order_id..."
                            spellcheck="false"
                            @keydown.enter="forcePaymentPaid()"
                        />
                    </div>

                    <!-- Quick actions -->
                    <div class="actions">
                        <button class="action-btn pay" :disabled="loading" @click="forcePaymentPaid('force-pay')">
                            <Zap :size="12" /> force-pay
                        </button>
                        <button class="action-btn" :disabled="loading" @click="forcePaymentPaid('force-unpay')">unpay</button>
                        <button class="action-btn" :disabled="loading" @click="forceOrderStatus('pending')">pending</button>
                        <button class="action-btn" :disabled="loading" @click="forceOrderStatus('confirmed')">confirmed</button>
                        <button class="action-btn" :disabled="loading" @click="forceOrderStatus('ready')">ready</button>
                        <button class="action-btn" :disabled="loading" @click="forceOrderStatus('done')">done</button>
                        <button class="action-btn cancel" :disabled="loading" @click="forceOrderStatus('cancelled')">cancel</button>
                    </div>

                    <!-- Log -->
                    <div class="log-area">
                        <div v-for="(entry, i) in log" :key="i" class="log-line" :class="entry.type">
                            <span class="log-ts">{{ entry.ts }}</span> {{ entry.msg }}
                        </div>
                        <div v-if="log.length === 0" class="log-empty">ctrl+shift+q to toggle</div>
                    </div>
                </div>
            </div>
        </transition>
    </teleport>
</template>

<style scoped>
.hacker-overlay {
    position: fixed;
    inset: 0;
    z-index: 9999;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    background: rgba(0,0,0,0.5);
    padding: 16px;
}

.hacker-panel {
    width: 100%;
    max-width: 430px;
    background: #0a0e17;
    border: 1px solid #1a3a2a;
    border-radius: 12px;
    padding: 14px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 12px;
    color: #00ff88;
    max-height: 60vh;
    display: flex;
    flex-direction: column;
}

.panel-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    color: #00ff88;
}

.header-title {
    flex: 1;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1.5px;
}

.close-btn {
    background: none;
    border: none;
    color: #555;
    cursor: pointer;
    padding: 4px;
}

.input-row {
    margin-bottom: 10px;
}

.picker-row {
    display: flex;
    gap: 6px;
}

.order-input {
    width: 100%;
    background: #0d1117;
    border: 1px solid #1a3a2a;
    border-radius: 6px;
    padding: 10px 12px;
    color: #00ff88;
    font-family: inherit;
    font-size: 12px;
    outline: none;
}

.order-input::placeholder {
    color: #2a5a3a;
}

.order-input:focus {
    border-color: #00ff88;
}

.actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 12px;
}

.action-btn {
    padding: 6px 10px;
    border-radius: 4px;
    border: 1px solid #1a3a2a;
    background: #0d1117;
    color: #00cc66;
    font-family: inherit;
    font-size: 11px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
}

.action-btn:hover:not(:disabled) {
    background: #1a3a2a;
}

.action-btn:disabled {
    opacity: 0.4;
}

.action-btn.pay {
    background: #0a2a1a;
    border-color: #00ff88;
    color: #00ff88;
    font-weight: 700;
}

.action-btn.cancel {
    border-color: #3a1a1a;
    color: #ff4444;
}

.log-area {
    flex: 1;
    overflow-y: auto;
    max-height: 200px;
    border-top: 1px solid #1a3a2a;
    padding-top: 8px;
}

.log-line {
    padding: 2px 0;
    line-height: 1.5;
    word-break: break-all;
}

.log-ts {
    color: #335533;
    margin-right: 6px;
}

.log-line.success { color: #00ff88; }
.log-line.error { color: #ff4444; }
.log-line.info { color: #888; }

.log-empty {
    color: #2a5a3a;
    text-align: center;
    padding: 20px 0;
}

/* Transition */
.panel-slide-enter-active,
.panel-slide-leave-active {
    transition: all 0.2s ease;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
    opacity: 0;
    transform: translateY(20px);
}
</style>
