<script>
import ComingSoon from '@/components/coming-soon/ComingSoon.vue'

export default {
    components: { ComingSoon },
}
</script>

<template>
    <!-- One full screen, no shared layout: LayoutJoin's padding would push it past the fold. -->
    <ComingSoon />
</template>
