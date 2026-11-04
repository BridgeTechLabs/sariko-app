// "+84900000001" (stored) -> "0900 000 001" (how Vietnamese read a number); anything else unchanged.
export function displayPhone(phone) {
    const local = (phone || '').replace(/^\+84/, '0')
    return /^0\d{9,10}$/.test(local) ? `${local.slice(0, 4)} ${local.slice(4, 7)} ${local.slice(7)}` : phone || ''
}
