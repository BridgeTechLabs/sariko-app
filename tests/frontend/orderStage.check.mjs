// 20261106-order-scheduled TC-3: node tests/frontend/orderStage.check.mjs
import assert from 'node:assert/strict'
import { cookingDay, isScheduled } from '../../frontend/src/utils/orderStage.js'

// Delivery Saturday 2026-11-14 18:00 VN, dishes need 2 days -> cooking starts Thursday 2026-11-12.
const order = { status: 'confirmed', preorder_days: 2, delivery_appointment: '2026-11-14T11:00:00+00:00' }
const wed2359 = Date.parse('2026-11-11T23:59:00+07:00')
const thu0000 = Date.parse('2026-11-12T00:00:00+07:00')

assert.equal(cookingDay(order), '2026-11-12')
assert.equal(isScheduled(order, wed2359), true)
assert.equal(isScheduled(order, thu0000), false)
assert.equal(isScheduled({ ...order, status: 'pending' }, wed2359), false)
assert.equal(isScheduled({ ...order, status: 'ready' }, wed2359), false)
assert.equal(isScheduled({ ...order, preorder_days: null }, wed2359), false)
assert.equal(isScheduled({ ...order, delivery_appointment: null }, wed2359), false)
// Appointment early morning VN (previous day in UTC) still counts by the Vietnam day.
assert.equal(cookingDay({ ...order, delivery_appointment: '2026-11-13T18:30:00+00:00' }), '2026-11-12')
console.log('orderStage: all checks passed')
