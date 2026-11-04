// Checks the DEV sign-in message filter (src/lib/devSessionMessage.js): node scripts/test-dev-session.mjs
import assert from 'node:assert/strict'
import { parseSessionMessage, SESSION_MESSAGE } from '../src/lib/devSessionMessage.js'

const ok = { type: SESSION_MESSAGE, access_token: 'a', refresh_token: 'r', redirect: '/seller/home' }
assert.deepEqual(parseSessionMessage('https://admin-dev.sariko.store', ok), { access_token: 'a', refresh_token: 'r', redirect: '/seller/home' })
assert.ok(parseSessionMessage('http://localhost:8093', ok))
for (const origin of ['https://admin.sariko.store', 'https://evil.example', 'http://localhost', 'https://localhost:8093',
    'https://admin-dev.sariko.store.evil.example', 'http://admin-dev.sariko.store', 'null']) {
    assert.equal(parseSessionMessage(origin, ok), null, origin)
}
for (const data of [null, 'x', { ...ok, type: 'other' }, { ...ok, access_token: '' }, { ...ok, refresh_token: 5 }]) {
    assert.equal(parseSessionMessage('https://admin-dev.sariko.store', data), null, JSON.stringify(data))
}
for (const redirect of ['//evil.example/x', 'https://evil.example', 'javascript:alert(1)', undefined]) {
    assert.equal(parseSessionMessage('https://admin-dev.sariko.store', { ...ok, redirect }).redirect, '/', String(redirect))
}
console.log('dev session message: ok')
