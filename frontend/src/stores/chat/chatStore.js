import { defineStore } from "pinia"
import { supabase } from "@/lib/supabase"
import { useAuthStore } from "@/stores/auth/authStore"
import apiChat from "@/apis/chat/apiChat"

// Reads/subscribes to messages go DIRECT to Supabase (RLS-protected, low latency).
// Conversation list, unread counts and mark-read go through the backend.

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

            _messageChannel: null,      // realtime channel for the open conversation
            _globalChannel: null,       // realtime channel for app-wide unread badge
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

        async loadConversations(asSeller = false) {
            try {
                this.loadingConversations = true
                const res = await apiChat.getConversations(asSeller)
                const list = res?.data?.conversations || []
                this.conversations = list
                this.totalUnread = list.reduce((sum, c) => sum + (c.unread_count || 0), 0)
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
            this.subscribeToConversation(conversationId)
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
                this.messages = data || []
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
                this._pushMessage(data)   // instant local echo; realtime echo is de-duped
            } catch (e) {
                console.error(`chatStore - sendMessage - ${e}`)
                throw e
            } finally {
                this.sending = false
            }
        },

        // Realtime + RLS: the socket must carry the user's JWT, otherwise the
        // server treats it as anon and RLS drops every change event. supabase-js
        // usually sets this on sign-in, but we re-assert it before subscribing to
        // avoid a race with async session restore.
        _ensureRealtimeAuth() {
            const token = useAuthStore().session?.access_token
            if (token) supabase.realtime.setAuth(token)
        },

        subscribeToConversation(conversationId) {
            this.unsubscribeFromConversation()
            this._ensureRealtimeAuth()
            this._messageChannel = supabase
                .channel(`conv:${conversationId}`)
                .on('postgres_changes',
                    { event: 'INSERT', schema: 'public', table: 'chat_messages',
                      filter: `conversation_id=eq.${conversationId}` },
                    ({ new: msg }) => {
                        this._pushMessage(msg)
                        // incoming message while the thread is open → read immediately
                        if (msg.sender_id !== this.myId) this.markRead(conversationId)
                    })
                .subscribe()
        },

        unsubscribeFromConversation() {
            if (this._messageChannel) {
                supabase.removeChannel(this._messageChannel)
                this._messageChannel = null
            }
        },

        // Sign-out: close both realtime channels, then drop the old account's conversations
        reset() {
            this.unsubscribeFromConversation()
            this.unsubscribeGlobalUnread()
            this.$reset()
        },

        closeConversation() {
            this.unsubscribeFromConversation()
            this.currentConversationId = null
            this.messages = []
        },

        // App-wide unread badge. A broad subscription with no conversation filter —
        // RLS on chat_messages delivers only rows in the caller's own conversations.
        subscribeGlobalUnread() {
            if (this._globalChannel) return
            this._ensureRealtimeAuth()
            this._globalChannel = supabase
                .channel('chat:global-unread')
                .on('postgres_changes',
                    { event: 'INSERT', schema: 'public', table: 'chat_messages' },
                    ({ new: msg }) => {
                        if (msg.sender_id === this.myId) return
                        if (msg.conversation_id === this.currentConversationId) return
                        this.totalUnread += 1
                        const conv = this.conversations.find(c => c.id === msg.conversation_id)
                        if (conv) {
                            conv.unread_count = (conv.unread_count || 0) + 1
                            conv.last_message_text = msg.body
                            conv.last_message_at = msg.created_at
                        }
                    })
                .subscribe()
        },

        unsubscribeGlobalUnread() {
            if (this._globalChannel) {
                supabase.removeChannel(this._globalChannel)
                this._globalChannel = null
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
            if (this.messages.some(m => m.id === msg.id)) return   // de-dupe realtime echo
            this.messages.push(msg)
        },
    },
})
