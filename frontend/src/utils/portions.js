// T134 (docs/dev/daily-portions Q7): portions left today of a same-day dish with a daily limit.
// null = no number to show: no limit, or a pre-order dish (checked for its delivery day when the order is placed).
export function portionsLeftToday(food) {
    if (!food?.daily_portions || food.preorder_day > 0) return null
    return food.remaining_today ?? food.daily_portions
}

// T181 A34: a pre-order dish with a daily limit, sold from its first delivery day: { n, date: 'dd/mm' } of that day,
// or null. Never blocks ordering (a later day may still have portions).
export function preorderPortions(food) {
    const date = food?.portions_date
    if (!food?.daily_portions || !date || food.remaining_preorder == null) return null
    return { n: food.remaining_preorder, date: dayMonth(date) }
}

// 'YYYY-MM-DD' -> 'dd/mm'
export const dayMonth = (date) => `${date.slice(8, 10)}/${date.slice(5, 7)}`
