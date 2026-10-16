<script>
import { mapState } from 'pinia';
import { useChatStore } from '@/stores/chat/chatStore';

export default {
    computed: {
        ...mapState(useChatStore, ['messages', 'loadingMessages', 'myId']),
    },

    watch: {
        'messages.length'() {
            this.$nextTick(() => {
                this.$refs.bottom?.scrollIntoView({ block: 'end' });
            });
        },
    },

    methods: {
        isMine(msg) {
            return msg.sender_id === this.myId;
        },
        formatTime(iso) {
            if (!iso) return '';
            return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
        },
    },
}
</script>

<template>
    <div class="bubble-list">
        <template v-if="loadingMessages && messages.length === 0">
            <q-skeleton type="rect" width="60%" height="36px" class="skeleton-in" animation="pulse" />
            <q-skeleton type="rect" width="50%" height="36px" class="skeleton-out" animation="pulse" />
            <q-skeleton type="rect" width="55%" height="36px" class="skeleton-in" animation="pulse" />
        </template>

        <div v-else-if="messages.length === 0" class="empty-thread">
            {{ $t('chat.empty_thread') }}
        </div>

        <div
            v-for="msg in messages"
            :key="msg.id"
            class="bubble-row"
            :class="isMine(msg) ? 'mine' : 'theirs'"
        >
            <div class="bubble">
                <div class="bubble-body">{{ msg.body }}</div>
                <div class="bubble-time">{{ formatTime(msg.created_at) }}</div>
            </div>
        </div>

        <div ref="bottom"></div>
    </div>
</template>

<style lang="scss" scoped>
.bubble-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.bubble-row {
    display: flex;
}

.bubble-row.mine {
    justify-content: flex-end;
}

.bubble-row.theirs {
    justify-content: flex-start;
}

.bubble {
    max-width: 78%;
    padding: 8px 12px;
    border-radius: 16px;
    font-size: 14px;
    line-height: 1.35;
    word-break: break-word;
}

.mine .bubble {
    background: #f5A623;
    color: #121b2f;
    border-bottom-right-radius: 4px;
}

.theirs .bubble {
    background: var(--surface, #1f2940);
    color: #fff;
    border-bottom-left-radius: 4px;
}

.bubble-time {
    margin-top: 2px;
    font-size: 10px;
    opacity: 0.6;
    text-align: right;
}

.empty-thread {
    text-align: center;
    color: rgb(122, 140, 174);
    font-size: 13px;
    padding: 40px 20px;
}

.skeleton-in {
    border-radius: 16px;
    align-self: flex-start;
}

.skeleton-out {
    border-radius: 16px;
    align-self: flex-end;
}
</style>
