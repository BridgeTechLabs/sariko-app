<script>
export default {
    props: {
        status: { type: String, required: true },
    },
}
</script>

<template>
    <span class="chip" :class="`chip-${status}`">{{ $t(`complaints.status.${status}`) }}</span>
</template>

<style scoped>
.chip {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    white-space: nowrap;
}

.chip-received  { background: rgba(245, 158, 11, 0.15); color: var(--color-warning); }
.chip-verifying { background: rgba(59, 130, 246, 0.15); color: var(--color-info); }
.chip-resolved  { background: rgba(34, 197, 94, 0.15);  color: var(--color-success); }
</style>
