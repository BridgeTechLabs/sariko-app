// The AI Studio post a buyer came from (docs/dev/20261123-studio-integration QĐ-1). A post link opens
// /seller/<slug>?ref=<post>&utm_source=<channel>; the last tap wins and stays after an order, so a reorder within
// the window also counts. The backend decides what is kept; same patterns as its CHECKs.
const KEY = 'sariko.ref'

export function saveStudioRef(slug, query) {
    const ref = query.ref
    if (typeof ref !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(ref)) return
    const source = typeof query.utm_source === 'string' && /^[a-z0-9_]{1,32}$/.test(query.utm_source) ? query.utm_source : null
    try { localStorage.setItem(KEY, JSON.stringify({ slug, ref, source, at: Date.now() })) } catch { }
}

// The order fields, or {} when there is none.
export function studioRefFields() {
    try {
        const { slug, ref, source, at } = JSON.parse(localStorage.getItem(KEY)) || {}
        return ref ? { ref_code: ref, ref_source: source, ref_slug: slug, ref_at: at } : {}
    } catch {
        return {}
    }
}
