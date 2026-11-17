<script>
import { formatVnd, optionsLines } from '@/utils/priceDisplay'

// A line's options under the dish name (cart, buyer and seller orders): one row per group,
// a group with several picks = its name, then one indented row per pick; the extra price on the right.
export default {
    name: 'OptionLines',
    props: {
        options: { type: Array, default: null },   // options_snapshot / the cart line's options
    },
    computed: {
        lines() { return optionsLines(this.options) },
    },
    methods: { formatVnd },
}
</script>

<template>
    <div v-if="lines.length" class="option-lines">
        <div v-for="(line, n) in lines" :key="n" class="option-row" :class="{ 'option-row--sub': line.sub }">
            <span>{{ line.label }}</span><span v-if="line.extra !== null">+{{ formatVnd(line.extra) }}</span>
        </div>
    </div>
</template>

<style lang="scss" scoped>
.option-lines {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin: -2px 0 4px;   /* tucked under the dish row; the cart card sets its own */
}

.option-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    font-size: 11px;
    color: var(--text-secondary);

    span:last-child { flex-shrink: 0; white-space: nowrap; }
}

.option-row--sub { padding-left: 12px; }
</style>
