<template>
    <div class="edit-profile-page">

        <slot name="EditProfileTopBar" />

        <div class="body">
            <slot name="EditProfilePhoto" />
            <slot name="EditProfileForm" />
        </div>

        <slot name="EditProfileSaveBar" />

    </div>
</template>

<style scoped>
.edit-profile-page {
    min-height: 100vh;
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    background: var(--background);
    font-family: var(--font-family-sans);
}

.body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-24);
    padding: var(--space-8) var(--space-24) var(--space-24);
}
</style>
