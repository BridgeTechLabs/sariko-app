<script>
import LayoutBaseEditProfile from '@/layouts/v2/account/LayoutBaseEditProfile.vue';
import EditProfileTopBar from '@/components/v2/account/edit-profile/EditProfileTopBar.vue';
import EditProfilePhoto from '@/components/v2/account/edit-profile/EditProfilePhoto.vue';
import EditProfileForm from '@/components/v2/account/edit-profile/EditProfileForm.vue';
import EditProfileSaveBar from '@/components/v2/account/edit-profile/EditProfileSaveBar.vue';

export default {
    name: 'EditProfilePageV2',
    components: {
        LayoutBaseEditProfile,
        EditProfileTopBar,
        EditProfilePhoto,
        EditProfileForm,
        EditProfileSaveBar,
    }
}
</script>

<template>
    <LayoutBaseEditProfile>

        <template #EditProfileTopBar>
            <EditProfileTopBar />
        </template>

        <template #EditProfilePhoto>
            <EditProfilePhoto />
        </template>

        <template #EditProfileForm>
            <EditProfileForm />
        </template>

        <template #EditProfileSaveBar>
            <EditProfileSaveBar />
        </template>

    </LayoutBaseEditProfile>
</template>
