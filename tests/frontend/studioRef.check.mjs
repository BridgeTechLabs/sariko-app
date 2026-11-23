// studio-integration QĐ-1 (docs/dev/20261123-studio-integration): node tests/frontend/studioRef.check.mjs
// A post link's ?ref is kept per the backend's patterns, the last tap wins, a bad source becomes null, a bad ref is ignored.
import assert from 'node:assert/strict'

const store = {}
globalThis.localStorage = { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = String(v) } }
const { saveStudioRef, studioRefFields } = await import('../../frontend/src/utils/studioRef.js')

assert.deepEqual(studioRefFields(), {})
saveStudioRef('nora', { ref: 'Ab3_x-9', utm_source: 'fb' })
const first = studioRefFields()
assert.equal(first.ref_code, 'Ab3_x-9'); assert.equal(first.ref_source, 'fb'); assert.equal(first.ref_slug, 'nora')
assert.ok(Math.abs(Date.now() - first.ref_at) < 1000)

for (const ref of ['a b', 'x'.repeat(65), ['a', 'b'], '']) saveStudioRef('other', { ref, utm_source: 'zalo' })
assert.equal(studioRefFields().ref_slug, 'nora', 'a bad ref leaves the last good one')

saveStudioRef('teresa', { ref: 'bio', utm_source: 'Facebook' })
assert.deepEqual({ ...studioRefFields(), ref_at: 0 }, { ref_code: 'bio', ref_source: null, ref_slug: 'teresa', ref_at: 0 })

store['sariko.ref'] = '{not json'
assert.deepEqual(studioRefFields(), {})
globalThis.localStorage = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') } }
saveStudioRef('nora', { ref: 'p1' })
assert.deepEqual(studioRefFields(), {})
console.log('studioRef: all checks passed')
