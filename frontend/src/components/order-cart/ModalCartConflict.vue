<script>
import { ShoppingCart, Trash2, X } from 'lucide-vue-next';
import { mapState, mapGetters, mapWritableState, mapActions } from 'pinia';
import { useCartStore } from "@/stores/cart/cartStore"
export default {
    components: {
        ShoppingCart, Trash2, X
    },

    computed: {
        ...mapWritableState(useCartStore, [
            "isShowModalCartConflict"
        ]),

        ...mapState(useCartStore, [
            "firstSeller",
            "secondSeller"
        ]),

        ...mapGetters(useCartStore, [
            "itemCount"
        ])
    },

    methods: {
        ...mapActions(useCartStore, [
            "clearCartAndAddItem"
        ]),

        goToCart() {
            this.isShowModalCartConflict = false
            this.$router.push('/cart')
        },

        async onClearAndAdd() {
            await this.clearCartAndAddItem()
        }
    }
}
</script>

<!-- Mounted once in App.vue: the store page, the dish page and the home page all add to the cart -->
<template>
  <q-dialog v-model="isShowModalCartConflict">
    <div class="modal-container">

        <div class="header-icon">
            <ShoppingCart>
                <q-badge color="red" floating></q-badge>
            </ShoppingCart>
        </div>
    
        <div class="header-title">
            {{ $t('cart_page.modal_cart_conflict.title_header') }}
        </div>

        <div class="text-message">
            {{ $t('cart_page.modal_cart_conflict.text_message_1') }}
            <span style="font-weight: 700; color: white;">{{firstSeller}}</span>.
            {{ $t('cart_page.modal_cart_conflict.text_message_2') }}
            <span style="font-weight: 800; color: white;">{{secondSeller}}</span>.
        </div>

        <div class="section-button-go-to-cart">
            <q-btn class="button-go-to-cart" no-caps flat @click="goToCart">
                <ShoppingCart class="icon-cart" />   
                <span>{{ $t('cart_page.modal_cart_conflict.button_label_go_to_cart') }}</span>
            </q-btn>
        </div>

        <div class="section-button-clear-cart">
            <q-btn class="button-trash" no-caps flat @click="onClearAndAdd">
                <Trash2 class="icon-trash"/>
                <span>{{ $t('cart_page.modal_cart_conflict.button_label_clear_cart') }}</span>
            </q-btn>
        </div>

        <div class="section-button-cancel">
            <q-btn class="button-cancel" no-caps flat @click="isShowModalCartConflict=false">
                <X /><span>{{ $t('common.button_label_cancel') }}</span>
            </q-btn>
        </div>

    </div>
  </q-dialog>
</template>

<style lang="scss" scoped>

.modal-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    font-family: $sariko-font-family-secondary;
    background-color: $bg-surface;
    padding: 20px;
}

.header-button {
    width: 100%;
    display: flex;
    justify-content: flex-end;
}

.header-icon {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 12px;
    background-color: #393025;
    border-radius: 50%;
    color: $accent;
    border: 1px solid #7d6e31;
    margin-bottom: 20px;
}

.header-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 20px;
}

.text-message {
    margin-bottom: 20px;
    font-weight: 500;
    color: rgb(255, 255, 255, 0.6)
}

.section-button-go-to-cart {
    display: flex;
    justify-content: center;
    width: 100%;
    margin-bottom: 10px;
}

.button-go-to-cart {
    width: 100%;
    background-color: $accent;
    color: var(--bg-main);
    font-weight: 600;
    border-radius: .75rem;
    padding: 10px 0px;
}

.icon-cart {
    margin-right: 10px;
}

.section-button-clear-cart {
    display: flex;
    justify-content: center;
    width: 100%;
    margin-bottom: 10px;
}

.button-trash {
    width: 100%;
    color: red;
    background-color: #540505;
    font-weight: 600;
    border-radius: .75rem;
    padding: 10px 0px;
}

.section-button-cancel {
    display: flex;
    justify-content: center;
    width: 100%;
    margin-bottom: 10px;
}

.button-cancel {
    width: 100%;
    color: rgb(255, 255, 255, .5);
    font-weight: 600;
    border-radius: .75rem;
    padding: 10px 0px;
}

.icon-trash {
    margin-right: 10px;
}

</style>