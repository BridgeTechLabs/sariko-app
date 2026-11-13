// 20261112-seller-menu đợt 2 S2 (QĐ2-9, TC2-26): node tests/frontend/stock.check.mjs
import assert from 'node:assert/strict'
import { minShortByFood, stockLeft } from '../../frontend/src/utils/portions.js'

// 1 Coca + 1 Pepsi of a dish with minimum 3: together 2, short, and BOTH rows are named by the dish id
assert.deepEqual(minShortByFood([{ id: 'a', quantity: 1, minQuantity: 3 }, { id: 'a', quantity: 1, minQuantity: 3 }]), { a: 3 })
// Rows add up to the minimum: fine
assert.deepEqual(minShortByFood([{ id: 'a', quantity: 2, minQuantity: 3 }, { id: 'a', quantity: 1, minQuantity: 3 }]), {})
// Another dish at its own minimum 1 is never short; an empty cart has nothing short
assert.deepEqual(minShortByFood([{ id: 'b', quantity: 1, minQuantity: 1 }]), {})
assert.deepEqual(minShortByFood([]), {})
// stock: null = no limit (not 0), 0 stays 0
assert.equal(stockLeft({ stock: null }), null)
assert.equal(stockLeft({}), null)
assert.equal(stockLeft({ stock: 0 }), 0)
console.log('stock: all checks passed')
