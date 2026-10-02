<script>
import { Plus, Minus, Star } from 'lucide-vue-next';
import { useCartStore } from '@/stores/cart/cartStore.js';

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
        itemPriceText: {
            required: true,
            type: String,
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
        itemVariantId: {
            required: false,
            type: String,
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
        }
    },

    components: {
        Plus, Minus, Star
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

        totalPriceText() {
            if (!this.itemPrice) return '—'
            const total = this.itemPrice * this.itemQuantity
            return new Intl.NumberFormat('vi-VN').format(total) + ' ₫'
        }
    },

    methods: {
        async onClickPlus() {
            await this.cartStore.updateQuantity(this.itemId, this.itemQuantity + 1, this.itemVariantId)
        },
        async onClickMinus() {
            if (this.itemQuantity <= 1) {
                await this.cartStore.removeItem(this.itemId, this.itemVariantId)
            } else {
                await this.cartStore.updateQuantity(this.itemId, this.itemQuantity - 1, this.itemVariantId)
            }
        }
    }
}
</script>

<template>

    <div class="background">
        <div class="container">

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
                            </div>
                            <div class="item-category">
                                <div>{{ itemCategory }}</div> &nbsp; | &nbsp; <Star color="#f5A623" size="12px"/> &nbsp; 4.5
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