// Short order code shared by buyer, seller and admin ("#48C0284C"): the first 8 hex digits
// of the order id, upper-cased, so everyone quotes the same code to support.
export const orderCode = id => (id ? '#' + id.slice(0, 8).toUpperCase() : '')
