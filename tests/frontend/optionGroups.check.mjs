// 20261112-seller-menu đợt 3 G2b (QĐ3-11, TC3-70 / TC3-71): node tests/frontend/optionGroups.check.mjs
import assert from 'node:assert/strict'
import { copyGroupForDish } from '../../frontend/src/utils/optionGroups.js'

function fakeApi(failCreate, failOrder = false) {
    const calls = []
    return {
        calls,
        detachOptionGroup: async (dish, g) => calls.push(['detach', dish, g]),
        attachOptionGroup: async (dish, g) => calls.push(['attach', dish, g]),
        orderOptionGroups: async (dish, ids) => {
            calls.push(['order', dish, ids])
            if (failOrder) throw new Error('order failed')
        },
        createOptionGroup: async (dish, body) => {
            calls.push(['create', dish, body.name])
            if (failCreate) throw new Error('groups_per_store_max')
            return { group: { id: 'copy' } }
        },
    }
}

// TC3-70: the copy takes the old group's place; only this dish is touched
let api = fakeApi(false)
const group = await copyGroupForDish(api, 'dish', ['a', 'old', 'b'], 'old', { name: 'Drinks' })
assert.equal(group.id, 'copy')
assert.deepEqual(api.calls, [['detach', 'dish', 'old'], ['create', 'dish', 'Drinks'], ['order', 'dish', ['a', 'copy', 'b']]])

// TC3-71: the create fails -> the old group goes back in its old place, the error reaches the form
api = fakeApi(true)
await assert.rejects(copyGroupForDish(api, 'dish', ['a', 'old', 'b'], 'old', { name: 'Drinks' }), /groups_per_store_max/)
assert.deepEqual(api.calls, [['detach', 'dish', 'old'], ['create', 'dish', 'Drinks'], ['attach', 'dish', 'old'], ['order', 'dish', ['a', 'old', 'b']]])
// Only the reorder fails: the copy is made (it stays last) and no error reaches the form, so Save is not retried
api = fakeApi(false, true)
assert.equal((await copyGroupForDish(api, 'dish', ['a', 'old', 'b'], 'old', { name: 'Drinks' })).id, 'copy')
assert.deepEqual(api.calls.map(c => c[0]), ['detach', 'create', 'order'])
console.log('optionGroups: all checks passed')
