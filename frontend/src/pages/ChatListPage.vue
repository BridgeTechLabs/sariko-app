<script>
import { ArrowLeft } from 'lucide-vue-next';
import LayoutBaseChatList from '@/layouts/chat/LayoutBaseChatList.vue';
import ConversationList from '@/components/chat/ConversationList.vue';
import { useChatStore } from '@/stores/chat/chatStore';
import { useAuthStore } from '@/stores/auth/authStore';

export default {
    name: 'ChatListPage',
    components: { LayoutBaseChatList, ConversationList, ArrowLeft },

    mounted() {
        const asSeller = !!useAuthStore().user?.isSeller;
        const chat = useChatStore();
        chat.loadConversations(asSeller);
        chat.subscribeGlobalUnread();
    },

    methods: {
        goBack() {
            const isSeller = !!useAuthStore().user?.isSeller;
            this.$router.push({ name: isSeller ? 'seller-home' : 'home' });
        },
    },
}
</script>

<template>
    <LayoutBaseChatList>
        <template #Header>
            <div class="header">
                <button class="back-btn" @click="goBack"><ArrowLeft :size="22" /></button>
                <div class="title">{{ $t('chat.inbox_title') }}</div>
            </div>
        </template>

        <template #List>
            <ConversationList />
        </template>
    </LayoutBaseChatList>
</template>

<style lang="scss" scoped>
.header {
    display: flex;
    align-items: center;
    gap: 12px;
    color: #fff;
}

.back-btn {
    background: none;
    border: none;
    color: #fff;
    display: flex;
    cursor: pointer;
}

.title {
    font-family: $sariko-font-family-primary;
    font-size: 20px;
    font-weight: 700;
}
</style>
