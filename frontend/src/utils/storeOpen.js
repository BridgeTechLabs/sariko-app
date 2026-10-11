// Mirrors backend apis/orders.py STORE_CLOSED_DETAIL: a closed store blocks same-day dishes
// (preorder_day 0) but still takes pre-orders.
export function blockedByClosedStore(seller, preorderDay) {
    return seller?.is_open === false && !(preorderDay > 0)
}
