// 20261112-seller-menu đợt 3 G2 (QĐ3-8, TC3-31): node tests/frontend/options.check.mjs
import assert from 'node:assert/strict'
import { optionsLines, picksOnDetail } from '../../frontend/src/utils/priceDisplay.js'

const snap = [{ group: 'Drinks', option: 'Coca-cola', extra_price: 5000 },
              { group: 'Extras', option: 'Fried egg', extra_price: 5000 },
              { group: 'Extras', option: 'Rice', extra_price: 0 }]
// One pick: one row with its price apart; several picks: the group's name, then a row per pick with its own price
assert.deepEqual(optionsLines(snap), [
    { label: 'Drinks: Coca-cola', extra: 5000, sub: false },
    { label: 'Extras', extra: null, sub: false },
    { label: 'Fried egg', extra: 5000, sub: true },
    { label: 'Rice', extra: 0, sub: true }])
assert.deepEqual(optionsLines(null), [])     // an order before option groups
// The quick "+" adds only a dish with nothing to pick
assert.equal(picksOnDetail({ food_item_variants: [], option_groups: [] }), false)
assert.equal(picksOnDetail({ option_groups: [{ id: 'g' }] }), true)
assert.equal(picksOnDetail({ food_item_option_groups: [{ group_id: 'g' }] }), true)   // featured dishes
assert.equal(picksOnDetail({ food_item_variants: [{ id: 'v' }] }), true)
console.log('options: all checks passed')
