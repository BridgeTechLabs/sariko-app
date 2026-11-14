import { defineStore } from "pinia"
import { supabase } from "@/lib/supabase"
import { useAuthStore } from "@/stores/auth/authStore"
import apiChat from "@/apis/chat/apiChat"
import { createPoller } from "@/composables/createPoller"

// Messages are read and sent DIRECT to Supabase (RLS-protected). Conversation list, unread counts and mark-read go
// through the backend. New messages arrive by polling (createPoller: paused while the tab is hidden), and only while
// the screen that shows them is open; the app-wide unread badge has no poll, see refreshUnread.
const CONVERSATIONS_POLL_MS = 15_000   // the conversation list, while ChatListPage is open
const MESSAGES_POLL_MS = 10_000        // the open conversation
const UNREAD_REFRESH_MIN_MS = 60_000   // the badge refreshes (app open, tab shown, page change) at most this often

export const useChatStore = defineStore("chatStore", {
    state() {
        return {
            conversations: [],          // [{ id, unread_count, last_message_text, ... }]
            currentConversationId: null,
            messages: [],               // open conversation, ascending by created_at
            totalUnread: 0,

            loadingConversations: false,
            loadingMessages: false,
            sending: false,

            _messagesPoller: null,      // new messages of the open conversation
            _conversationsPoller: null, // conversation list, while ChatListPage is open
            _conversationsLoadedAt: 0,  // last time the list was read, any source
        }
    },

    getters: {
        myId() {
            return useAuthStore().user?.id || null
        },
    },

    actions: {

        // Buyer entry point: open (or reuse) the conversation with a seller.
        async startConversation(sellerSlug) {
            const res = await apiChat.createConversation(sellerSlug)
            return res?.data?.conversation || null
        },

        async loadConversations(asSeller = false, { silent = false } = {}) {
            try {
                if (!silent) this.loadingConversations = true
                const res = await apiChat.getConversations(asSeller)
                const list = res?.data?.conversations || []
                this.conversations = list
                this.totalUnread = list.reduce((sum, c) => sum + (c.unread_count || 0), 0)
                this._conversationsLoadedAt = Date.now()
                return list
            } catch (e) {
                console.error(`chatStore - loadConversations - ${e}`)
                throw e
            } finally {
                this.loadingConversations = false
            }
        },

        async openConversation(conversationId) {
            this.currentConversationId = conversationId
            await this.loadMessages(conversationId)
            this.startWatchingMessages(conversationId)
            this.markRead(conversationId)
        },

        async loadMessages(conversationId) {
            try {
                this.loadingMessages = true
                const { data, error } = await supabase
                    .from('chat_messages')
                    .select('id, conversation_id, sender_id, body, created_at, read_at')
                    .eq('conversation_id', conversationId)
                    .order('created_at', { ascending: true })
                if (error) throw error
                if (conversationId === this.currentConversationId) this.messages = data || []   // A24a: not an older chat's
            } catch (e) {
                console.error(`chatStore - loadMessages - ${e}`)
                throw e
            } finally {
                this.loadingMessages = false
            }
        },

        async sendMessage(body) {
            const text = (body || '').trim()
            if (!text || !this.currentConversationId) return
            try {
                this.sending = true
                const { data, error } = await supabase
                    .from('chat_messages')
                    .insert({
                        conversation_id: this.currentConversationId,
                        sender_id: this.myId,
                        body: text,
                    })
                    .select('id, conversation_id, sender_id, body, created_at, read_at')
                    .single()
                if (error) throw error
                this._pushMessage(data)   // instant local echo; the poll may bring it again, de-duped
            } catch (e) {
                console.error(`chatStore - sendMessage - ${e}`)
                throw e
            } finally {
                this.sending = false
            }
        },

        startWatchingMessages(conversationId) {
            this.stopWatchingMessages()
            this._messagesPoller = createPoller({
                name: 'chat-messages',
                intervalMs: MESSAGES_POLL_MS,
                fetch: () => this.fetchNewMessages(conversationId),
            })
            this._messagesPoller.start()
        },

        stopWatchingMessages() {
            if (this._messagesPoller) {
                this._messagesPoller.stop()
                this._messagesPoller = null
            }
        },

        // Messages newer than the last one on screen; an incoming one in the open thread is read at once.
        async fetchNewMessages(conversationId) {
            const last = this.messages[this.messages.length - 1]?.created_at
            let query = supabase
                .from('chat_messages')
                .select('id, conversation_id, sender_id, body, created_at, read_at')
                .eq('conversation_id', conversationId)
                .order('created_at', { ascending: true })
            if (last) query = query.gt('created_at', last)
            const { data, error } = await query
            if (error) throw error
            if (conversationId !== this.currentConversationId) return
            const fresh = (data || []).filter(m => !this.messages.some(x => x.id === m.id))
            fresh.forEach(m => this._pushMessage(m))
            if (fresh.some(m => m.sender_id !== this.myId)) this.markRead(conversationId)
        },

        // Sign-out: stop both polls, then drop the old account's conversations
        reset() {
            this.stopWatchingMessages()
            this.stopWatchingConversations()
            this.$reset()
        },

        closeConversation() {
            this.stopWatchingMessages()
            this.currentConversationId = null
            this.messages = []
        },

        // Unread badge: no background poll. Called when the app opens, the tab is shown again and the page changes;
        // a read of the list from any source in the last minute is reused.
        refreshUnread() {
            if (Date.now() - this._conversationsLoadedAt < UNREAD_REFRESH_MIN_MS) return
            this._conversationsLoadedAt = Date.now()   // now, not on the answer: the app-open and first-page triggers fire together
            return this.loadConversations(!!useAuthStore().user?.isSeller, { silent: true }).catch(() => {})
        },

        // The conversation list screen: poll while it is open.
        startWatchingConversations() {
            if (this._conversationsPoller) return
            this._conversationsPoller = createPoller({
                name: 'chat-conversations',
                intervalMs: CONVERSATIONS_POLL_MS,
                fetch: () => this.loadConversations(!!useAuthStore().user?.isSeller, { silent: this.conversations.length > 0 }),
            })
            this._conversationsPoller.start()
        },

        stopWatchingConversations() {
            if (this._conversationsPoller) {
                this._conversationsPoller.stop()
                this._conversationsPoller = null
            }
        },

        async pinConversation(conversationId, pinned) {
            const conv = this.conversations.find(c => c.id === conversationId)
            if (!conv) return
            const prev = conv.pinned
            conv.pinned = pinned          // optimistic
            this._sortConversations()
            try {
                await apiChat.setPinned(conversationId, pinned)
            } catch (e) {
                conv.pinned = prev         // rollback
                this._sortConversations()
                console.error(`chatStore - pinConversation - ${e}`)
                throw e
            }
        },

        async deleteConversation(conversationId) {
            const idx = this.conversations.findIndex(c => c.id === conversationId)
            if (idx === -1) return
            const [removed] = this.conversations.splice(idx, 1)   // optimistic
            this.totalUnread = Math.max(0, this.totalUnread - (removed.unread_count || 0))
            if (this.currentConversationId === conversationId) this.closeConversation()
            try {
                await apiChat.deleteConversation(conversationId)
            } catch (e) {
                this.conversations.splice(idx, 0, removed)         // rollback
                this.totalUnread += removed.unread_count || 0
                console.error(`chatStore - deleteConversation - ${e}`)
                throw e
            }
        },

        // Mirror the backend ordering: pinned first, then most recent activity.
        _sortConversations() {
            this.conversations.sort((a, b) => {
                if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1
                return new Date(b.last_message_at || 0) - new Date(a.last_message_at || 0)
            })
        },

        async markRead(conversationId) {
            const conv = this.conversations.find(c => c.id === conversationId)
            const wasUnread = conv?.unread_count || 0
            try {
                await apiChat.markRead(conversationId)
                if (conv) conv.unread_count = 0
                this.totalUnread = Math.max(0, this.totalUnread - wasUnread)
            } catch (e) {
                console.error(`chatStore - markRead - ${e}`)
            }
        },

        _pushMessage(msg) {
            if (!msg) return
            if (this.messages.some(m => m.id === msg.id)) return   // de-dupe the local echo
            this.messages.push(msg)
        },
    },
})
