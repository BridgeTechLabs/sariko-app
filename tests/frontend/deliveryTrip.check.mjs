// T187 (docs/dev/20261110-delivery-failed ponytail): node tests/frontend/deliveryTrip.check.mjs
// The buyer tracker's "trip still running" uses the one list of ended trip statuses (CANCELLED was missing).
import assert from 'node:assert/strict'
import { DELIVERY_TERMINAL, isTripActive } from '../../frontend/src/utils/deliveryBadge.js'

for (const s of ['ASSIGNING_DRIVER', 'ON_GOING', 'PICKED_UP']) assert.equal(isTripActive(s), true, s)
for (const s of DELIVERY_TERMINAL) assert.equal(isTripActive(s), false, s)
assert.ok(DELIVERY_TERMINAL.includes('CANCELLED') && DELIVERY_TERMINAL.includes('CANCELED'))
assert.equal(isTripActive(undefined), false)
console.log('deliveryTrip: all checks passed')
