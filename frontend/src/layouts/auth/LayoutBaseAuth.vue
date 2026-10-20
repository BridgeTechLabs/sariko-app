<script>
</script>

<template>
    <!-- The auth page is always dark (#121b2f below): dark tokens for everything inside,
         or the light theme puts navy text on this navy background. -->
    <div class="background" data-theme="dark">

        <div class="container">

            <div class="section-auth-header">
                <slot name="AuthHeader" />
            </div>

            <div class="section-auth-button-group">
                <slot name="AuthButtonGroup" />
            </div>

            <div class="section-auth-input-fields">
                <slot name="AuthInputFields" />
            </div>

        </div>

    </div>
</template>

<style scoped>

.background {
    min-height: 100vh;
    min-height: 100dvh;
    height: fit-content;
    display: flex;
    flex-direction: column;
    align-items: center;
    background-color: #121b2f;
    color: var(--text-primary); /* re-resolved inside data-theme="dark"; body's colour is the light one */
    padding: 50px 0px 100px 0px;
}

.container {
    width: 100%;
}

.section-auth-header {
    margin-bottom: 20px;
}

.section-auth-button-group {
    width: 100%;
    margin-bottom: 20px;
}
</style>