// T187 (docs/dev/20261110-delivery-failed ponytail): node tests/frontend/deliveryTrip.check.mjs
// The buyer tracker's "trip still running" uses the one list of ended trip statuses (CANCELLED was missing).
import assert from 'node:assert/strict'
import { DELIVERY_TERMINAL, isTripActive, readySubtextKey } from '../../frontend/src/utils/deliveryBadge.js'

for (const s of ['ASSIGNING_DRIVER', 'ON_GOING', 'PICKED_UP']) assert.equal(isTripActive(s), true, s)
for (const s of DELIVERY_TERMINAL) assert.equal(isTripActive(s), false, s)
assert.ok(DELIVERY_TERMINAL.includes('CANCELLED') && DELIVERY_TERMINAL.includes('CANCELED'))
assert.equal(isTripActive(undefined), false)
// T193: the sub-line of a ready delivery order follows the trip
assert.equal(readySubtextKey('ON_GOING'), 'delivery_tracker.status_subtext_ON_GOING')
assert.equal(readySubtextKey('PICKED_UP'), 'delivery_tracker.status_subtext_PICKED_UP')
for (const s of ['ASSIGNING_DRIVER', undefined, null, 'SOMETHING_NEW']) assert.equal(readySubtextKey(s), 'delivery_tracker.status_subtext_ready', String(s))
console.log('deliveryTrip: all checks passed')
