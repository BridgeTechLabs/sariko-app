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

// A level or options to pick: the quick "+" opens the dish page instead of adding (featured dishes carry
// food_item_option_groups, the menu option_groups)
export function picksOnDetail(food) {
    return hasVariants(food) || (food?.option_groups || food?.food_item_option_groups || []).length > 0
}

/**
 * The options of a cart or order line, [{group, option, extra_price}], as rows with the price apart (shown right,
 * in the price column; a free option shows +0 ₫). One pick: one row "Drinks: Coca-cola". Several picks in a group:
 * the group's name, then one indented row per pick with its own price (Jack 13/11).
 * -> [{ label, extra, sub }], extra null = no price (the group's name row).
 */
export function optionsLines(options) {
    const groups = new Map()
    for (const o of options || []) groups.set(o.group, [...(groups.get(o.group) || []), o])
    return [...groups].flatMap(([group, picks]) => picks.length === 1
        ? [{ label: `${group}: ${picks[0].option}`, extra: Number(picks[0].extra_price), sub: false }]
        : [{ label: group, extra: null, sub: false },
           ...picks.map((o) => ({ label: o.option, extra: Number(o.extra_price), sub: true }))])
}
