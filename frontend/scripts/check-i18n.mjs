// Compile every vue-i18n message in src/i18n/locales/*.json; exit 1 if one fails.
// vite build does not catch these (messages compile at runtime): a raw @ broke sign-in on
// PROD 2026-10-16. Literal @ { } | must be written {'@'} {'{'} {'|'}. Runs before vite build.
import { baseCompile } from '@intlify/message-compiler'
import fs from 'node:fs'
import path from 'node:path'

const dir = path.join(path.dirname(new URL(import.meta.url).pathname), '..', 'src', 'i18n', 'locales')
let bad = 0
for (const file of fs.readdirSync(dir).filter((f) => f.endsWith('.json'))) {
    const walk = (node, prefix) => {
        for (const [k, v] of Object.entries(node)) {
            if (typeof v === 'string') {
                baseCompile(v, { onError: (e) => { bad++; console.log(`${file} ${prefix}${k} ${e.message}`) } })
            } else if (v && typeof v === 'object') {
                walk(v, `${prefix}${k}.`)
            }
        }
    }
    walk(JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8')), '')
}
if (bad) {
    console.log(`${bad} compile error(s) in the messages above`)
    process.exit(1)
}
console.log('all messages compile')
