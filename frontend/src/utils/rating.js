// One way to show a star score everywhere: "4.5", always one decimal.
export const ratingText = avg => (avg == null ? '' : Number(avg).toFixed(1))
