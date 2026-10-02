<script>
import {
    Search, MapPin, ChevronDown, ChevronRight, SlidersHorizontal, Plus, House, Receipt, ShoppingBag,
    Bell, User, Clock, ArrowRight, History, Store, Heart, Star, BadgeCheck, ArrowLeft, Share2,
    MessageCircle, Minus, Info, Utensils, Package, Check, CreditCard, Banknote, Calendar, Phone,
    Truck, X, RefreshCw, Trash2, Lock, Camera, CircleHelp, Send, Globe, Moon, LogOut, Pencil,
    Shield, Cake, Snowflake, Plane, Sparkles, Shirt, Baby, Leaf, Lamp, Copy, TriangleAlert,
    Volume2, Eye,
} from 'lucide-vue-next';

// Figma "🎨 System / Icons" → lucide. Keys are the Figma names without the "icon/" prefix.
const ICONS = {
    'search': Search,
    'map-pin': MapPin,
    'chevron-down': ChevronDown,
    'chevron-right': ChevronRight,
    'sliders': SlidersHorizontal,
    'plus': Plus,
    'home': House,
    'receipt': Receipt,
    'shopping-bag': ShoppingBag,
    'bell': Bell,
    'user': User,
    'clock': Clock,
    'arrow-right': ArrowRight,
    'history': History,
    'store': Store,
    'heart': Heart,
    'star': Star,
    'badge-check': BadgeCheck,
    'arrow-left': ArrowLeft,
    'share': Share2,
    'message-circle': MessageCircle,
    'minus': Minus,
    'info': Info,
    'utensils': Utensils,
    'package': Package,
    'check': Check,
    'credit-card': CreditCard,
    'banknote': Banknote,
    'calendar': Calendar,
    'phone': Phone,
    'truck': Truck,
    'x': X,
    'refresh': RefreshCw,
    'trash': Trash2,
    'lock': Lock,
    'camera': Camera,
    'help-circle': CircleHelp,
    'send': Send,
    'globe': Globe,
    'moon': Moon,
    'log-out': LogOut,
    'pencil': Pencil,
    'shield': Shield,
    'cake': Cake,
    'snowflake': Snowflake,
    'plane': Plane,
    'sparkles': Sparkles,
    'shirt': Shirt,
    'baby': Baby,
    'leaf': Leaf,
    'lamp': Lamp,
    'copy': Copy,
    'alert-triangle': TriangleAlert,
    'volume': Volume2,
    'eye': Eye,
}

// Color comes from `color` (currentColor) of the parent
export default {
    props: {
        name: {
            type: String,
            required: true,
            validator: (value) => value in ICONS,
        },
        size: {
            type: Number,
            default: 24,
        },
        filled: {
            type: Boolean,
            default: false,
        },
    },

    computed: {
        icon() {
            return ICONS[this.name]
        },

        // Figma strokes scale with the icon: 2 at 24px, 1.5 at 18px, 1.33 at 16px
        strokeWidth() {
            return this.size / 12
        },
    },
}
</script>

<template>
    <component
        :is="icon"
        class="base-icon"
        :size="size"
        :stroke-width="strokeWidth"
        :fill="filled ? 'currentColor' : 'none'"
        aria-hidden="true"
    />
</template>

<style scoped>
.base-icon {
    flex-shrink: 0;
}
</style>
