<script>
import { Phone } from 'lucide-vue-next';
import { useAuthStore } from '@/stores/auth/authStore';

export default {
    components: {
        Phone
    },

    computed: {
        phone: {
            get() {
                return useAuthStore().inputPhoneNumber
            },
            set(value) {
                useAuthStore().inputPhoneNumber = value
            }
        }
    }
}
</script>

<template>

    <div class="container-phone-number">

        <div class="title">
            <Phone class="icon-phone"/> {{ $t('onboarding_page.buyer.section_phone_number.title') }}
        </div>

        <!-- Leading 0 or not, the backend normalizes to +84… -->
        <div class="input-container">
            <q-input
            class="input"
            dense
            outlined
            type="tel"
            prefix="+84"
            placeholder="901 234 567"
            color="white"
            bg-color="bgInputField"
            v-model="phone"
            />
        </div>

        <div class="tooltip">
            {{ $t('onboarding_page.buyer.section_phone_number.tooltip') }}
        </div>
    </div>

</template>

<style lang="scss" scoped>

.title {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
}

.icon-phone {
    margin-right: 8px;
}

.input-container {
    overflow: hidden;
    display: flex;
    align-items: center;
    width: 100%;
    margin-bottom: 10px;
}

.input {
    width: 100%;
}

.tooltip {
    color: var(--text-muted);
    font-size: 12px;
}

:deep(.q-field__native) {
    color: #ffffff;
}

</style>

<style lang="scss">

.input .q-field__control {
    border-radius: .75rem;
}
</style>