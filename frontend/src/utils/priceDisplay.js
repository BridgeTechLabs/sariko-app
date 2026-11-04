// VND format per the project convention (see CLAUDE.md).
export function formatVnd(amount) {
    return new Intl.NumberFormat('vi-VN').format(amount || 0) + ' ₫'
}

/**
 * What to show for a dish's price.
 *
 * A dish with price levels has no single price: food_items.price is a leftover
 * that stops meaning anything once levels exist, so it must never be shown.
 * Sold-out levels are excluded — a range must not advertise a price nobody can buy.
 *
 * Always formatted from the number: the stored price_text is never shown (docs/dev/vnd-format Q1).
 * Returns "50.000 ₫" for one price, "50.000 ₫ – 80.000 ₫" for several.
 */
export function foodPriceDisplay(food) {
    const levels = (food?.food_item_variants || []).filter(v => v.is_available !== false)
    if (!levels.length) return formatVnd(food?.price)

    const prices = levels.map(v => Number(v.price))
    const min = Math.min(...prices)
    const max = Math.max(...prices)
    return min === max ? formatVnd(min) : `${formatVnd(min)} – ${formatVnd(max)}`
}

export function hasVariants(food) {
    return (food?.food_item_variants || []).length > 0
}
