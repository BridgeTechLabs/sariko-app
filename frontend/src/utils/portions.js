// A dish's stock (dish stock, ADR 0004): portions the seller can still sell, null = no limit.
// The API also says sold_out (stock under the dish's minimum per order), so screens never compare the two themselves.
export const stockLeft = (food) => food?.stock ?? null

// Dishes whose cart rows add up to less than their minimum per order: { foodId: minimum } (QĐ2-9).
// rows = [{ id, quantity, minQuantity }]; one dish can be several rows (other options), so the quantities are summed.
export function minShortByFood(rows) {
    const total = {}
    for (const r of rows) total[r.id] = (total[r.id] || 0) + r.quantity
    return Object.fromEntries(rows.filter(r => total[r.id] < r.minQuantity).map(r => [r.id, r.minQuantity]))
}
