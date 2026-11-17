// Build check: every name a .vue template reads must be declared by its script (props, data, computed, methods,
// setup, inject, <script setup>, or a mapState / mapGetters / mapActions list). An imported function the template
// calls but the component never exposes compiles fine and then breaks the render at runtime (B3b, OrderDetailDialog).
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { compileScript, compileTemplate, parse } from '@vue/compiler-sfc'

const BROWSER = new Set(['window', 'document', 'console', 'navigator', 'location', 'localStorage', 'process'])
const files = (dir) => readdirSync(dir).flatMap((f) => {
    const p = join(dir, f)
    return statSync(p).isDirectory() ? files(p) : p.endsWith('.vue') ? [p] : []
})

// Names that vuex / pinia helpers add: mapState(store, ['a', 'b']) or mapState(store, { a: ..., b: ... })
function mapped(script) {
    const names = new Set()
    for (const m of script.matchAll(/\bmap\w+\(\s*[\w.()]+\s*,\s*(\[[^\]]*\]|\{[^}]*\})/g)) {
        for (const n of m[1].matchAll(/['"]?([A-Za-z_$][\w$]*)['"]?\s*(?:[,:\]}]|$)/g)) names.add(n[1])
    }
    return names
}

let bad = 0
for (const file of files(process.argv[2] || 'src')) {
    const { descriptor } = parse(readFileSync(file, 'utf8'))
    if (!descriptor.template || !(descriptor.script || descriptor.scriptSetup)) continue
    const { bindings = {}, content } = compileScript(descriptor, { id: file })
    const known = mapped(content)
    const { code } = compileTemplate({ source: descriptor.template.content, filename: file, id: file, compilerOptions: { bindingMetadata: bindings } })
    for (const name of new Set([...code.matchAll(/_ctx\.([A-Za-z_$][\w$]*)/g)].map((m) => m[1]))) {
        if (name.startsWith('$') || name in bindings || known.has(name) || BROWSER.has(name)) continue
        console.error(`${file}: the template uses "${name}" but the script does not declare it`)
        bad++
    }
}
if (bad) process.exit(1)
console.log('check-template-names: ok')
