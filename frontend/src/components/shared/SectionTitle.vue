<!-- The one group title style of the seller pages (Jack 09/11: like "SETTINGS" on Me): uppercase grey,
     outside the card it heads. -->
<template>
    <div class="section-title"><slot /></div>
</template>

<style scoped>
.section-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
    padding-left: 4px;
}
</style>
