<script>
import { User } from 'lucide-vue-next';

export default {
    props: {
        sellerIndex: {
            type: Number
        },
        sellerName: {
            type: String,
            required: true
        },
        sellerSlugName: {
            type: String,
            required: true
        },
        sellerAvatarImageURL: {
            type: String,
        },
        sellerFeaturedCategory: {
            type: String,
            required: true
        },
        sellerStatus: {
            type: String,
            default: 'active'
        },
        sellerIsOpen: {
            type: Boolean,
            default: true
        }
    },

    components: {
        User
    },

    computed: {
        isComingSoon() {
            return this.sellerStatus === 'coming_soon'
        }
    },

    methods: {
        onClicked() {
            this.$router.push(`/seller/${this.sellerSlugName}`)
        }
    }
}
</script>

<template>

    <div v-on:click="onClicked" :class="[sellerIndex == 1 ? 'container-1st' : 'container', { muted: isComingSoon }]">

        <div class="seller-avatar">
            <q-avatar v-if="sellerAvatarImageURL" size="48px">
                <img :src="sellerAvatarImageURL" class="avatar-img">
            </q-avatar>
            <div v-else class="guest-icon">
                <User :size="28" />
            </div>
        </div>

        <div class="seller-info">
            <div class="seller-name">
                {{ sellerName }}
            </div>

            <div class="seller-feature-category">
                🍲 {{ sellerFeaturedCategory }}
            </div>

            <div class="seller-index">
                <q-badge
                v-if="isComingSoon"
                rounded
                class="badge badge-coming-soon"
                :label="$t('seller_card.coming_soon')"/>
                <q-badge
                v-else-if="!sellerIsOpen"
                rounded
                class="badge badge-coming-soon"
                :label="$t('seller_card.closed')"/>
                <q-badge
                v-else
                rounded
                class="badge"
                :label="'# ' + sellerIndex"/>
            </div>
        </div>

    </div>

</template>

<style lang="scss" scoped>

.container-1st {
    display: flex;
    align-items: center;
    border: 1px solid $accent;
    border-radius: .75rem;
    background-color: #2c261f;
    padding: 10px 14px;
    cursor: pointer;
}

.container {
    display: flex;
    align-items: center;
    border: 1.5px solid rgb(255, 255, 255, 0.3);
    border-radius: .75rem;
    background-color: rgb(255, 255, 255, 0.15);
    padding: 10px 14px;
    cursor: pointer;
}

.seller-avatar {
    margin-right: 10px;
}

.avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.guest-icon {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    border: 1px solid rgba(255, 255, 255, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(255, 255, 255, 0.6);
}

.seller-name {
    font-weight: 700;
    font-size: 10px;
}

.seller-feature-category {
    font-size: 8px;
    color: rgb(122, 140, 174)
}

.badge {
    padding: 5px 10px;
    font-size: 9px;
    color: #facc15;
    background-color: #4a391f;
}

// Coming-soon kitchens stay tappable (they open the coming-soon page) but read as not orderable yet
.muted {
    opacity: 0.5;
    filter: grayscale(1);
}

.badge-coming-soon {
    color: #7a8cae;
    background-color: rgba(122, 140, 174, 0.18);
}


</style>