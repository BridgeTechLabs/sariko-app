<script>
import { Plus, Minus } from 'lucide-vue-next';
import { useCartStore } from '@/stores/cart/cartStore.js';
import { apiErrorMessage } from '@/lib/axiosPolicy.js';
import { formatVnd, optionsLines } from '@/utils/priceDisplay';

export default {
    props: {
        itemId: {
            required: true,
            type: String,
        },
        itemName: {
            required: true,
            type: String,
        },
        itemPrice: {
            required: true,
            type: Number,
        },
        itemCategory: {
            required: true,
            type: String,
        },
        itemImgSrc: {
            required: true,
            type: String,
        },
        itemQuantity: {
            required: true,
            type: Number
        },
        // The cart row's id: +/- and remove name the row, one dish can have several
        rowKey: {
            required: true,
            type: String
        },
        itemOptions: {
            type: Array,
            default: () => []
        },
        // The server's reason this row can't be ordered as it is (an option off, removed, a group now required)
        itemProblem: {
            type: Object,
            default: null
        },
        itemVariantName: {
            required: false,
            type: String,
            default: null
        },
        sellerStore: {
            require: true,
            type: String
        },
        sellerSlugName: {
            require: true,
            type: String
        },
        portionsLeft: {
            required: false,
            type: Number,
            default: null
        },
        itemUnavailable: {
            type: Boolean,
            default: false
        }
    },

    components: {
        Plus, Minus
    },

    setup() {
        const cartStore = useCartStore()
        return { cartStore }
    },

    computed: {
        singlePriceText() {
            if (!this.itemPrice) return '—'
            return new Intl.NumberFormat('vi-VN').format(this.itemPrice) + ' ₫'
        },

        optionLines() {
            return optionsLines(this.itemOptions)
        },

        problemText() {
            return this.itemProblem ? apiErrorMessage({ detail: this.itemProblem }) : ''
        },

        totalPriceText() {
            if (!this.itemPrice) return '—'
            const total = this.itemPrice * this.itemQuantity
            return new Intl.NumberFormat('vi-VN').format(total) + ' ₫'
        }
    },

    methods: {
        formatVnd,
        async onClickPlus() {
            await this.cartStore.updateQuantity(this.rowKey, this.itemQuantity + 1)
        },
        async onClickMinus() {
            if (this.itemQuantity <= 1) {
                await this.cartStore.removeItem(this.rowKey)
            } else {
                await this.cartStore.updateQuantity(this.rowKey, this.itemQuantity - 1)
            }
        },
        // The row goes and the dish page opens to pick the options again
        async chooseAgain() {
            await this.cartStore.removeItem(this.rowKey)
            this.$router.push(`/food/${this.sellerSlugName}/${this.itemId}`)
        }
    }
}
</script>

<template>

    <div class="background">
        <div :class="['container', { unavailable: itemUnavailable, problem: itemProblem }]">

            <div class="row q-gutter-md">

                <div class="col-2">
                    <q-img
                    class="item-image"
                    sizes="12px"
                    :src="itemImgSrc"
                    />
                </div>

                <div class="col">

                    <div class="item-metadata">
                        <div class="group-1">
                            <div class="item-name">
                                {{ itemName }}
                                <span v-if="itemVariantName" class="item-variant">{{ itemVariantName }}</span>
                                <span v-if="itemUnavailable" class="item-sold-out">{{ $t('cart_page.sold_out_label') }}</span>
                                <span v-else-if="portionsLeft !== null && itemQuantity > portionsLeft" class="item-sold-out">{{ $t('cart_page.only_left', { n: portionsLeft }) }}</span>
                            </div>
                            <div v-for="line in optionLines" :key="line.label" class="option-row" :class="{ 'option-row--sub': line.sub }">
                                <span>{{ line.label }}</span><span v-if="line.extra !== null">+{{ formatVnd(line.extra) }}</span>
                            </div>
                            <div class="item-category">
                                <div>{{ itemCategory }}</div>
                            </div>
                            <div v-if="itemProblem" class="item-problem" role="alert">
                                <span>{{ problemText }}</span>
                                <q-btn flat dense no-caps class="choose-again" :label="$t('cart_page.choose_again')" @click="chooseAgain" />
                            </div>
                        </div>
                        <div class="group-2">
                            <div class="item-price">
                                <div class="item_price__total">{{ totalPriceText }}</div>
                                <div v-if="itemQuantity > 1" class="item_price__single">{{ singlePriceText }}</div>
                            </div>
                            <div class="item-quantity">
                                <div class="button-sub-quantity">
                                    <q-btn flat round dense size="10px" @click="onClickMinus">
                                        <Minus style="color: white; background-color: black; border-radius: 50%;"/>
                                    </q-btn>
                                </div>

                                <div class="item-price-text">
                                    <div>{{ itemQuantity }}</div>
                                </div>
                                <div class="button-add-quantity">
                                    <q-btn flat round dense size="10px" @click="onClickPlus">
                                        <Plus style="color: black; background-color: #f5A623; border-radius: 50%;"/>
                                    </q-btn>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                </div>

            </div>

        </div>
    </div>

</template>

<style lang="scss" scoped>

.background {
    padding: 5px 0px 0px 20px;
}

.container {
    font-family: $sariko-font-family-secondary;
    padding: 10px;
}

.item-image {
    border-radius: 1rem;
}

.item-metadata {
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.group-1 {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: flex-start;
}

.unavailable { opacity: 0.55; }

.problem {
    border: 1px solid #e5484d;
    border-radius: 12px;
}

.option-row {
    width: 100%;
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin: 2px 0;
    font-size: 11px;
    color: var(--text-secondary);

    span:last-child { flex-shrink: 0; white-space: nowrap; }
}

.option-row--sub { padding-left: 12px; }

.item-problem {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px 8px;
    margin: 4px 0;
    font-size: 12px;
    color: #e5484d;
    white-space: normal;
}

.choose-again {
    min-height: 32px;
    padding: 0 10px;
    border-radius: 999px;
    background: rgba(245, 166, 35, 0.15);
    color: #f5A623;
    font-size: 12px;
    font-weight: 600;
}

.item-sold-out {
    display: inline-block;
    margin-left: 6px;
    padding: 1px 8px;
    border-radius: 8px;
    background: rgba(229, 72, 77, 0.18);
    color: #e5484d;
    font-size: 11px;
    font-weight: 600;
}

.item-variant {
    display: inline-block;
    margin-left: 6px;
    padding: 1px 8px;
    border-radius: 8px;
    background: rgba(245, 166, 35, 0.15);
    color: #f5A623;
    font-size: 11px;
    font-weight: 600;
    vertical-align: middle;
}

.item-name {
    font-size: 12px;
    font-weight: 600;
    color: $accent;
}

.item-category {
    display: flex;
    align-items: center;
    font-size: 10px;
    font-weight: 600;
    color: rgb(255, 255, 255, 0.5);
}

.store-name {
    font-size: 10px;
    font-weight:600;
    color: var(--color-info)
}

.group-2 {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
}

.item-price {
    display: flex;
    align-items: baseline;
    font-size: 14px;
    font-weight: 600;
}

.item_price__single {
    margin-left: 10px;
    font-size: 10px;
    color: var(--text-muted);
}

.item-quantity {
    display: flex;
    width: 35%;
    justify-content: space-between;
    align-items: center;
    background-color: rgb(255, 255, 255, 0.2);
    padding: 0px 4px 1px 2px;
    border-radius: 1rem;
}

.button-add-quantity {
    // background-color: white;
    border-radius: 50%;
}

.button-sub-quantity {
    // background-color: white;
    border-radius: 50%;
}

</style>