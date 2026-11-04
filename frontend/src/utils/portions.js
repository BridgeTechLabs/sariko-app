// T134 (docs/dev/daily-portions Q7): portions left today of a same-day dish with a daily limit.
// null = no number to show: no limit, or a pre-order dish (checked for its delivery day when the order is placed).
export function portionsLeftToday(food) {
    if (!food?.daily_portions || food.preorder_day > 0) return null
    return food.remaining_today ?? food.daily_portions
}
