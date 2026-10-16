<script>
import { mapState } from 'pinia';
import { Notify } from 'quasar';
import { User, Search, Share2, Heart, Star, BadgeCheck, MessageCircle, ArrowLeft } from 'lucide-vue-next';
import { useSellerStore } from '@/stores/seller/sellerStore';
import { useAuthStore } from '@/stores/auth/authStore';
import { useChatStore } from '@/stores/chat/chatStore';

const DEFAULT_COVER = '/images/defaullt-kitchen-bg.jpg';

export default {
    components: { User, Search, Share2, Heart, Star, BadgeCheck, MessageCircle, ArrowLeft },

    data() {
        return {
            isFavorite: false,
            isOpeningChat: false,
        };
    },

    computed: {
        ...mapState(useSellerStore, ["seller", "totalItems"]),
        coverImage() {
            return this.seller?.cover_url || DEFAULT_COVER;
        },
        hasRating() {
            return this.seller?.rating_count > 0 && this.seller?.rating_avg != null;
        },
        isVerified() {
            return !!this.seller?.is_verified;
        },
        isOpen() {
            return !!this.seller?.is_open;
        },
        isOwnStore() {
            const auth = useAuthStore();
            const myProfileId = auth.sellerId || auth.user?.sellerId;
            return !!myProfileId && myProfileId === this.seller?.id;
        },
        hoursLabel() {
            const o = this.fmtTime(this.seller?.opening_time);
            const c = this.fmtTime(this.seller?.closing_time);
            return (o && c) ? `${o}–${c}` : null;
        },
        distanceLabel() {
            const auth = useAuthStore();
            const raw = [auth.inputLat, auth.inputLon, this.seller?.lat, this.seller?.lon];
            // Number(null) === 0 (finite!), which would place a missing coordinate at
            // (0,0) off Africa → a bogus ~11800km reading. Reject null/''/NaN first.
            if (raw.some(v => v == null || v === '' || !Number.isFinite(Number(v)))) return null;
            const [bLat, bLon, sLat, sLon] = raw.map(Number);

            const R = 6371; // km
            const toRad = d => d * Math.PI / 180;
            const dLat = toRad(sLat - bLat);
            const dLon = toRad(sLon - bLon);
            const a = Math.sin(dLat / 2) ** 2 +
                Math.cos(toRad(bLat)) * Math.cos(toRad(sLat)) * Math.sin(dLon / 2) ** 2;
            const km = R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
            return km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1)} km`;
        },
    },

    methods: {
        fmtTime(t) {
            if (!t) return null;
            const [h, m] = String(t).split(':');
            if (h == null || m == null) return null;
            return `${Number(h)}:${m}`;
        },
        goBack() {
            if (window.history.length > 1) this.$router.back();
            else this.$router.push({ name: 'home' });
        },
        goSearch() {
            this.$router.push({ name: 'search' });
        },
        async share() {
            const url = window.location.href;
            const title = this.seller?.store_name || 'Sariko';
            try {
                if (navigator.share) {
                    await navigator.share({ title, url });
                } else {
                    await navigator.clipboard.writeText(url);
                    Notify.create({ message: this.$t('seller_page.link_copied'), color: 'positive', timeout: 1500 });
                }
            } catch (e) {
                // user dismissed the share sheet — ignore
            }
        },
        toggleFavorite() {
            // TODO: persist to a favorites table once it exists — local-only for now
            this.isFavorite = !this.isFavorite;
        },
        async chatWithSeller() {
            const auth = useAuthStore();
            if (!auth.user) {
                this.$router.push({ name: 'signin', query: { redirect: this.$route.fullPath } });
                return;
            }
            try {
                this.isOpeningChat = true;
                const slug = this.seller?.slug || this.$route.params.slugName;
                const conv = await useChatStore().startConversation(slug);
                if (conv) {
                    this.$router.push({ name: 'conversation', params: { conversationId: conv.id } });
                }
            } catch (e) {
                console.error(`SellerInfo - chatWithSeller - ${e}`);
            } finally {
                this.isOpeningChat = false;
            }
        },
    },
}
</script>

<template>
    <div class="hero-header">

        <!-- Full-bleed cover -->
        <div class="hero">
            <img :src="coverImage" class="hero-img" :alt="seller?.store_name ? `${seller.store_name} cover` : ''">
            <div class="hero-scrim"></div>

            <button class="hero-btn hero-back" @click="goBack" :aria-label="$t('seller_page.aria_back')">
                <ArrowLeft :size="18" />
            </button>

            <div class="hero-actions">
                <button class="hero-btn" @click="goSearch" :aria-label="$t('seller_page.aria_search')"><Search :size="18" /></button>
                <button class="hero-btn" @click="share" :aria-label="$t('seller_page.aria_share')"><Share2 :size="18" /></button>
                <button class="hero-btn" @click="toggleFavorite" :aria-pressed="isFavorite" :aria-label="$t('seller_page.aria_favorite')">
                    <Heart :size="18" :fill="isFavorite ? '#f5A623' : 'none'" :color="isFavorite ? '#f5A623' : '#fff'" />
                </button>
            </div>
        </div>

        <!-- Store info card overlapping the cover -->
        <div class="info-card">

            <div class="identity">
                <div class="avatar-ring">
                    <q-avatar size="84px">
                        <img v-if="seller?.avatar_url" :src="seller.avatar_url" class="avatar-img">
                        <div v-else class="avatar-fallback"><User :size="34" /></div>
                    </q-avatar>
                    <q-badge rounded class="status" :class="isOpen ? 'is-open' : 'is-closed'">
                        <span class="status-dot"></span>{{ isOpen ? 'Open' : 'Closed' }}
                    </q-badge>
                </div>

                <!-- Row 1: store name (left) + open/closed status (right) -->
                <div class="name-row">
                    <div class="store-name">
                        <span class="store-name__label">{{ seller?.store_name }}</span>
                        <BadgeCheck v-if="isVerified" :size="18" class="verified-check" />
                    </div>
                </div>

                <div v-if="seller && !isOpen" class="closed-notice">{{ $t('seller_page.closed_notice') }}</div>

                <!-- Row 2: meta line (left) + chat button (right) -->
                <div class="meta-row">
                    <div class="status-line">
                        <template v-if="!hasRating">
                            <span class="founding">{{ $t('seller_page.founding_seller') }}</span>
                            <span class="dot-sep"></span>
                        </template>

                        <span>{{ $t('seller_page.item_count', totalItems, { count: totalItems }) }}</span>

                        <template v-if="distanceLabel">
                            <span class="dot-sep"></span>
                            <span class="distance">{{ distanceLabel }}</span>
                        </template>

                        <template v-if="hasRating">
                            <span class="dot-sep"></span>
                            <span class="rating">
                                <Star :size="13" fill="#f5A623" color="#f5A623" />
                                {{ seller.rating_avg }}
                                <span class="rating-count">
                                    ({{ $t('common.rating_count', seller.rating_count, { count: seller.rating_count }) }})
                                </span>
                            </span>
                        </template>
                    </div>

                    <button v-if="!isOwnStore" class="chat-btn" :disabled="isOpeningChat" @click="chatWithSeller">
                        <q-spinner-dots v-if="isOpeningChat" color="dark" size="1.4em" />
                        <template v-else>
                            <MessageCircle :size="17" />
                            <span>{{ $t('seller_page.btn_chat') }}</span>
                        </template>
                    </button>
                </div>
            </div>

        </div>

    </div>
</template>

<style lang="scss" scoped>
/* break out of LayoutBaseSellerPage padding (10px background + 10px section) so the hero is full-bleed */
.hero-header {
    margin: -10px -20px 0;
}

/* ---------- Cover ---------- */
.hero {
    position: relative;
    width: 100%;
    height: 176px;
    overflow: hidden;
}

.hero-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}

/* keeps the top controls legible on bright photos and blends into the card */
.hero-scrim {
    position: absolute;
    inset: 0;
    background:
        linear-gradient(to bottom, rgba(18, 27, 47, 0.45) 0%, rgba(18, 27, 47, 0) 32%),
        linear-gradient(to top, rgba(18, 27, 47, 0.55) 0%, rgba(18, 27, 47, 0) 40%);
    pointer-events: none;
}

.hero-actions {
    position: absolute;
    top: calc(12px + env(safe-area-inset-top, 0px));
    right: 12px;
    display: flex;
    gap: 8px;
    z-index: 2;
}

.hero-back {
    position: absolute;
    top: calc(12px + env(safe-area-inset-top, 0px));
    left: 12px;
    z-index: 2;
}

.hero-btn {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: none;
    background: rgba(18, 27, 47, 0.55);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background 0.15s ease, transform 0.1s ease;

    &:active {
        background: rgba(18, 27, 47, 0.78);
        transform: scale(0.94);
    }
}

/* ---------- Info card ---------- */
.info-card {
    position: relative;
    margin-top: -20px;
    border-top-left-radius: 20px;
    border-top-right-radius: 20px;
    background: var(--surface, #1f2940);
    padding: 16px 16px 18px 16px;
}

.identity {
    display: flex;
    flex-direction: column;
    align-items: flex-start;     /* left-align the stack; also guards the avatar from stretching */
    padding: 0px 10px;
}

.avatar-ring {
    position: relative;         /* anchor for the Open/Closed status badge */
    display: flex;
    flex-shrink: 0;              /* never let a flex parent squeeze the avatar */
    width: 90px;
    height: 90px;               /* fixed box so a stretchy parent can't distort the circle */
    margin-top: -85px;        /* lift avatar so it straddles the cover / card seam */
    border-radius: 50%;
    padding: 3px;
    background: var(--bg-main, #121b2f);
    box-shadow: 0 0 0 2px rgba(245, 166, 35, 0.4);
    line-height: 0;
    box-sizing: border-box;
}

/* Row 1: name + status */
.name-row {
    display: flex;
    align-items: center;
    margin-top: 10px;
}

/* Row 2: meta line + chat button */
.meta-row {
    display: flex;
    align-items: flex-end;
    gap: 12px;
    width: 100%;
    margin-top: 5px;
}

.avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.avatar-fallback {
    width: 84px;
    height: 84px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-main, #121b2f);
    color: rgba(255, 255, 255, 0.55);
}

.store-name {
    flex: 1;                     /* take the row, push status to the right edge */
    min-width: 0;               /* allow the label to ellipsis instead of colliding */
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 6px;
    margin-right: 10px;
    font-family: $sariko-font-family-primary;
    font-size: 21px;
    font-weight: 700;
    line-height: 1.2;
    color: #fff;
}

.store-name__label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.verified-check {
    flex-shrink: 0;
    color: #3b82f6;
}

.status-line {
    flex: 1;                     /* take the row, push the chat button to the right edge */
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 7px;
    font-family: $sariko-font-family-secondary;
    font-size: 12.5px;
    font-weight: 600;
    color: rgb(139, 154, 184);
}

.status {
    position: absolute;         /* sit on the avatar (bottom-center) */
    bottom: -6px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 2;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: $sariko-font-family-secondary;
    font-size: 13px;
    font-weight: 700;
    padding: 4px 10px;
    background: var(--bg-main, #121b2f);
    white-space: nowrap;
}

.status.is-open {
    color: #48d77d;
    border: solid 1px #48d77d;
}

.status.is-closed {
    color: #e26d6d;
    border: solid 1px #e26d6d;
}

.rating {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    color: #f5A623;
}

.rating-count {
    color: rgba(255, 255, 255, 0.6);
    font-weight: 500;
    white-space: nowrap;
}

.founding {
    color: #ffd000;
    font-weight: 700;
}

.distance {
    color: rgba(255, 255, 255, 0.85);
}

.status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
}

.dot-sep {
    width: 2px;
    height: 11px;
    background: currentColor;
    opacity: 1;
}

/* ---------- Chat button (compact, right of the meta row) ---------- */
.chat-btn {
    flex-shrink: 0; 
    padding: 0 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    border: none;
    border-radius: 19px;
    background: #f5A623;
    color: #121b2f;
    font-family: $sariko-font-family-secondary;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 6px 16px -6px rgba(245, 166, 35, 0.5);
    transition: transform 0.1s ease, box-shadow 0.15s ease, opacity 0.15s ease;

    &:active {
        transform: translateY(1px);
        box-shadow: 0 3px 10px -6px rgba(245, 166, 35, 0.5);
    }

    &:disabled {
        opacity: 0.75;
        cursor: default;
        box-shadow: none;
    }
}

.closed-notice {
    margin-top: 6px;
    font-size: 12px;
    color: #f5A623;
}
</style>
