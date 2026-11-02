<script>
</script>

<template>

    <div class="background">

        <div class="main">

            <div class="seller-info-section">
                <slot name="SellerInfo" />
            </div>

            <q-separator class="seperator"/>

            <div class="categories-section">
                <slot name="Categories" />
            </div>

            <q-separator class="seperator"/>

            <div class="menu-section">
                <slot name="Menu" />
            </div>

            <div class="safe-area" style="height: calc(16px + env(safe-area-inset-bottom, 0px));" />

            <slot name="CartFab" />

        </div>

    </div>

</template>


<style scoped>
.background {
    width: 100%;
    padding: 10px;
}

.seller-info-section {
    margin-bottom: 10px;
    padding: 0px 10px;
}

.categories-section {
    width: 100%;
    display: flex;
    margin-bottom: 0px;
}

.seperator {
    background-color: #373c45;
    margin-bottom: 5px;
}

.menu-section {
    margin-top: 20px;
    /* the menu now grows with the page (no nested scroll area), so the last row
       needs clearance from the floating cart button */
    padding-bottom: calc(72px + env(safe-area-inset-bottom, 0px));
}

</style>