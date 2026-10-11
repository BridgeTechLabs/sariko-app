<script>
import LayoutBaseChangePassword from '@/layouts/v2/account/LayoutBaseChangePassword.vue';
import ChangePasswordTopBar from '@/components/v2/account/change-password/ChangePasswordTopBar.vue';
import ChangePasswordForm from '@/components/v2/account/change-password/ChangePasswordForm.vue';
import ChangePasswordSaveBar from '@/components/v2/account/change-password/ChangePasswordSaveBar.vue';

export default {
    name: 'ChangePasswordPageV2',
    components: {
        LayoutBaseChangePassword,
        ChangePasswordTopBar,
        ChangePasswordForm,
        ChangePasswordSaveBar,
    }
}
</script>

<template>
    <LayoutBaseChangePassword>

        <template #ChangePasswordTopBar>
            <ChangePasswordTopBar />
        </template>

        <template #ChangePasswordForm>
            <ChangePasswordForm />
        </template>

        <template #ChangePasswordSaveBar>
            <ChangePasswordSaveBar />
        </template>

    </LayoutBaseChangePassword>
</template>
