<script>
import { mapState, mapActions } from 'pinia';
import { User, MessageCircle, Pin, Trash2 } from 'lucide-vue-next';
import { useChatStore } from '@/stores/chat/chatStore';

// Pin is an always-visible button on the right of each row.
// Delete is hidden behind a left swipe (~1/4 of the row), then tapped.
const ACTION_W = 88;

export default {
    components: { User, MessageCircle, Pin, Trash2 },

    data() {
        return {
            openId: null,          // row with the Delete action revealed
            dragId: null,          // row being dragged right now
            dragBase: 0,           // offset the drag started from
            dragDx: 0,             // live horizontal delta
            dragging: false,       // horizontal gesture confirmed
            axisLocked: false,     // scroll-vs-swipe direction decided
            startX: 0,
            startY: 0,
            suppressClick: false,  // swallow the click that follows a drag
        };
    },

    computed: {
        ...mapState(useChatStore, ['conversations', 'loadingConversations']),
    },

    methods: {
        ...mapActions(useChatStore, ['pinConversation', 'deleteConversation']),

        partyName(conv) {
            return conv.seller_profiles?.store_name || conv.users?.name || 'Chat';
        },
        partyAvatar(conv) {
            return conv.seller_profiles?.avatar_url || conv.users?.avatar_url || null;
        },
        openConversation(conv) {
            this.$router.push({ name: 'conversation', params: { conversationId: conv.id } });
        },

        // ---- swipe-to-reveal (Delete only, leftward) ----
        offsetFor(id) {
            if (this.dragId === id) {
                return Math.max(-ACTION_W, Math.min(0, this.dragBase + this.dragDx));
            }
            if (this.openId === id) return -ACTION_W;
            return 0;
        },
        rowStyle(conv) {
            return {
                transform: `translateX(${this.offsetFor(conv.id)}px)`,
                transition: this.dragId === conv.id ? 'none' : 'transform 0.22s ease',
            };
        },
        onTouchStart(e, conv) {
            if (e.touches.length !== 1) return;
            this.startX = e.touches[0].clientX;
            this.startY = e.touches[0].clientY;
            this.dragId = conv.id;
            this.dragBase = this.openId === conv.id ? -ACTION_W : 0;
            this.dragDx = 0;
            this.dragging = false;
            this.axisLocked = false;
        },
        onTouchMove(e, conv) {
            if (this.dragId !== conv.id) return;
            const dx = e.touches[0].clientX - this.startX;
            const dy = e.touches[0].clientY - this.startY;
            if (!this.axisLocked) {
                if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
                this.axisLocked = true;
                this.dragging = Math.abs(dx) > Math.abs(dy);
                if (!this.dragging) { this.dragId = null; return; }   // vertical → let the list scroll
            }
            if (!this.dragging) return;
            e.preventDefault();          // horizontal drag: block vertical scroll
            this.dragDx = dx;
        },
        onTouchEnd(e, conv) {
            if (this.dragId !== conv.id) return;
            const offset = Math.max(-ACTION_W, Math.min(0, this.dragBase + this.dragDx));
            if (offset <= -ACTION_W * 0.4) this.openId = conv.id;         // Delete revealed
            else if (this.openId === conv.id) this.openId = null;
            this.suppressClick = this.dragging;
            this.dragId = null;
            this.dragDx = 0;
            this.dragging = false;
            this.axisLocked = false;
        },
        onRowClick(conv) {
            if (this.suppressClick) { this.suppressClick = false; return; }
            if (this.openId) { this.openId = null; return; }   // an open row → tap closes it
            this.openConversation(conv);
        },

        // ---- actions ----
        async onPin(conv) {
            this.openId = null;
            try {
                await this.pinConversation(conv.id, !conv.pinned);
            } catch (e) {
                this.$q.notify({ classes: 'quasar-notify-negative', message: this.$t('chat.toast_pin_failed'), position: 'bottom', timeout: 2000 });
            }
        },
        async onDelete(conv) {
            this.openId = null;
            try {
                await this.deleteConversation(conv.id);
            } catch (e) {
                this.$q.notify({ classes: 'quasar-notify-negative', message: this.$t('chat.toast_delete_failed'), position: 'bottom', timeout: 2000 });
            }
        },
    },
}
</script>

<template>
    <div>
        <!-- Skeleton -->
        <template v-if="loadingConversations && conversations.length === 0">
            <q-skeleton v-for="n in 5" :key="n" type="rect" height="64px" class="skeleton-row" animation="pulse" />
        </template>

        <!-- Empty -->
        <div v-else-if="conversations.length === 0" class="empty-state">
            <MessageCircle :size="40" />
            <div class="empty-title">{{ $t('chat.no_messages') }}</div>
            <div class="empty-sub">{{ $t('chat.empty_list_hint') }}</div>
        </div>

        <!-- List: Pin button on the right; swipe left → reveal Delete, then tap -->
        <div
            v-for="conv in conversations"
            :key="conv.id"
            class="swipe-wrap"
            @touchstart.passive="onTouchStart($event, conv)"
            @touchmove="onTouchMove($event, conv)"
            @touchend="onTouchEnd($event, conv)"
        >
            <!-- revealed on swipe left -->
            <button class="swipe-action delete" @click="onDelete(conv)">
                <Trash2 :size="20" />
                <span>{{ $t('chat.delete') }}</span>
            </button>

            <div class="conv-row" :style="rowStyle(conv)" @click="onRowClick(conv)">
                <q-avatar size="48px" class="conv-avatar">
                    <img v-if="partyAvatar(conv)" :src="partyAvatar(conv)" class="avatar-img">
                    <div v-else class="avatar-fallback"><User :size="22" /></div>
                </q-avatar>

                <div class="conv-body">
                    <div class="conv-name">{{ partyName(conv) }}</div>
                    <div class="conv-preview">{{ conv.last_message_text || $t('chat.no_messages') }}</div>
                </div>

                <q-badge v-if="conv.unread_count > 0" class="conv-unread" rounded>
                    {{ conv.unread_count }}
                </q-badge>

                <button
                    class="pin-btn"
                    :class="{ active: conv.pinned }"
                    :title="conv.pinned ? $t('chat.unpin') : $t('chat.pin')"
                    @click.stop="onPin(conv)"
                >
                    <Pin :size="18" />
                </button>
            </div>
        </div>
    </div>
</template>

<style lang="scss" scoped>
.skeleton-row {
    border-radius: 16px;
    margin-bottom: 8px;
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 64px 20px;
    color: rgb(122, 140, 174);
    text-align: center;
}

.empty-title {
    font-family: $sariko-font-family-primary;
    font-size: 16px;
    font-weight: 700;
    color: #fff;
}

.empty-sub {
    font-size: 12px;
}

.swipe-wrap {
    position: relative;
    overflow: hidden;
    border-radius: 16px;
    margin-bottom: 8px;
}

.swipe-action {
    position: absolute;
    top: 0;
    bottom: 0;
    right: 0;
    width: 88px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    border: none;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    background: #e53935;
    color: #fff;
}

.conv-row {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 12px;
    cursor: pointer;
    background: var(--bg-main, #040A14);
    will-change: transform;

    &:active {
        background: var(--bg-surface, #1f2940);
    }
}

.pin-btn {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: rgba(255, 255, 255, 0.3);
    cursor: pointer;
    transition: color 0.15s ease;

    &.active { color: #facc15; }

    &:active { background: var(--bg-surface, #1f2940); }
}

.conv-avatar {
    flex-shrink: 0;
}

.avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.avatar-fallback {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-surface, #1f2940);
    color: rgba(255, 255, 255, 0.6);
}

.conv-body {
    flex: 1;
    min-width: 0;
}

.conv-name {
    font-family: $sariko-font-family-primary;
    font-size: 15px;
    font-weight: 700;
    color: #fff;
}

.conv-preview {
    font-size: 13px;
    color: rgb(122, 140, 174);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.conv-unread {
    flex-shrink: 0;
    background: #facc15;
    color: #121b2f;
    font-weight: 700;
}
</style>
