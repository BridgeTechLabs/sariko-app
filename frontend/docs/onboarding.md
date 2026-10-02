# Frontend Onboarding — Sariko

Sariko là web app (PWA) chợ đồ ăn nhà làm. Tài liệu này giúp bạn đọc hiểu và sửa được code frontend.

---

## 1. Chạy project

```bash
cd frontend
cp .env.example .env.development   # điền VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
npm install
npm run dev                        # http://localhost:8081
```

Backend phải chạy ở `localhost:5000`. Mọi request `/rest/...` được Vite chuyển tiếp (proxy) sang backend — xem `vite.config.js`.

---

## 2. Framework đang dùng

| Thư viện | Dùng để làm gì |
|---|---|
| **Vue 3** | Framework UI. File `.vue` = `<script>` + `<template>` + `<style>`. Project dùng **Options API** (`data`, `computed`, `methods`, `mounted`) |
| **Vite** | Chạy dev server + build. Config: `vite.config.js` |
| **Quasar** | Bộ component UI có sẵn (`q-btn`, `q-input`, `q-skeleton`, `q-dialog`...) + `Notify` để hiện toast |
| **Pinia** | Store — nơi giữ dữ liệu dùng chung giữa các component (user, giỏ hàng, đơn hàng...) |
| **Vue Router** | Điều hướng URL → Page |
| **Axios** | Gọi HTTP tới backend |
| **Supabase JS** | Đăng nhập / đăng ký, lấy token |
| **vue-i18n** | Đa ngôn ngữ (English-PH + Tiếng Việt). Trong template dùng `$t('key')` |
| **Lucide Vue Next** | Icon (`import { Store } from 'lucide-vue-next'`) |
| **SCSS** | CSS có biến. Biến màu/font ở `src/assets/variables.scss`, tự động import vào mọi file |

Tài liệu nên đọc trước: [Vue 3 Options API](https://vuejs.org/guide/introduction.html) (chọn "Options" ở góc trái), [Pinia](https://pinia.vuejs.org/core-concepts/), [Quasar components](https://quasar.dev/vue-components).

---

## 3. Cấu trúc thư mục `src/`

```
src/
├── main.js          # Điểm khởi động: tạo app, tự load mọi file trong plugins/
├── App.vue          # Component gốc, chứa <router-view>, gắn axios interceptor
├── plugins/         # router.js, pinia.js, quasar.js, i18n.js
├── pages/           # 1 file = 1 màn hình (1 route)
├── layouts/         # Khung bố cục của page (vị trí, padding, slot)
├── components/      # Các khối UI + logic, chia folder theo page
├── stores/          # Pinia stores, chia theo domain (auth, cart, order, seller...)
├── apis/            # Hàm gọi backend, chia theo domain
├── lib/             # axiosPolicy.js (axios + token), supabase.js
├── composables/     # Hàm dùng lại: createPoller (polling), setLanguage
├── i18n/locales/    # en-PH.json, vi.json
├── utils/           # Hàm tiện ích nhỏ
└── assets/          # CSS, SCSS variables
```

Quy ước đặt tên folder: page `CartPage.vue` ↔ layout `layouts/order-cart/` ↔ components `components/order-cart/`.

---

## 4. Pattern chính: Page = Layout + Components

Mỗi màn hình gồm 3 lớp, mỗi lớp một việc:

| Lớp | Việc của nó | Không làm |
|---|---|---|
| **Page** (`pages/`) | Ghép Layout với Components qua slot | Không chứa UI chi tiết |
| **Layout** (`layouts/`) | Sắp xếp vị trí, padding, khi nào hiện section nào | Không gọi API |
| **Component** (`components/`) | Hiển thị + logic, đọc/ghi store trực tiếp | Không lo vị trí trên trang |

Ví dụ `pages/CartPage.vue`:

```vue
<LayoutBaseOrderCart>
    <template #CartItems>   <CartItems />   </template>
    <template #TotalAmount> <TotalAmounts /></template>
</LayoutBaseOrderCart>
```

Layout đặt `<slot name="CartItems" />` ở đúng chỗ. Tên slot viết **PascalCase**.

Component **không truyền dữ liệu qua props/events** — tất cả đọc/ghi thẳng vào Pinia store.

---

## 5. Luồng dữ liệu (data flow)

```
User click
  → Component (methods)
    → Store action (stores/)
      → API function (apis/)
        → apiClient (lib/axiosPolicy.js) — tự gắn token
          → Backend /rest/v1/...
      ← Store cập nhật state
  ← Component tự render lại (vì đọc state qua mapState)
```

Ví dụ thật — tải giỏ hàng:

1. `components/order-cart/CartItems.vue` → `mounted()` gọi `useCartStore().getCurrentCart()`
2. `stores/cart/cartStore.js` → `getCurrentCart()` gọi `apiCarts.getCart()`, rồi gán kết quả vào `this.cartItems`
3. `apis/cart/apiCart.js` → `apiClient.get('/v1/cart')`
4. `CartItems.vue` dùng `...mapState(useCartStore, ['cartItems'])` nên UI tự cập nhật

Cách component dùng store (Options API):

```js
import { mapState, mapActions } from 'pinia'
import { useCartStore } from '@/stores/cart/cartStore'

export default {
    computed: { ...mapState(useCartStore, ['cartItems', 'subtotalText']) },
    methods:  { ...mapActions(useCartStore, ['getCurrentCart']) },
}
```

---

## 6. Đăng nhập & phân quyền

- `lib/supabase.js`: client Supabase, dùng để signin/signup.
- `stores/auth/authStore.js`: giữ `user`, `session`. Hàm `bootstrap()` chạy **một lần** khi mở app: khôi phục session → tải profile, địa chỉ, giỏ hàng, đơn hàng.
- `lib/axiosPolicy.js`: interceptor tự gắn `Authorization: Bearer <token>` vào mọi request, và hiện toast khi lỗi. Bạn **không cần** tự gắn token.
- `plugins/router.js` → `router.beforeEach`: chặn route theo `meta`:
  - `requiresAuth` — chưa login → đẩy về `signin`
  - `guestOnly` — đã login → không vào trang auth nữa
  - `requiresSeller` — không phải seller → về `home`

Có 2 vai trò: **buyer** (các page ở `pages/`) và **seller** (các page ở `pages/seller/`).

---

## 7. Làm một tính năng mới — checklist

1. **Route**: thêm vào `plugins/router.js` (kèm `meta` nếu cần login)
2. **API**: thêm hàm vào `apis/<domain>/`, luôn dùng `apiClient`
3. **Store**: thêm state + action vào `stores/<domain>/`
4. **Components**: tạo trong `components/<ten-page>/`, đọc store bằng `mapState`
5. **Layout**: tạo trong `layouts/<ten-page>/`, khai báo các `<slot>`
6. **Page**: ghép layout + components
7. **Text**: thêm key vào **cả hai** `i18n/locales/en-PH.json` và `vi.json`, không hard-code chữ

---

## 8. Quy tắc cần nhớ

- Options API, **không** dùng Composition API (`<script setup>`).
- Icon: Lucide, không dán SVG trực tiếp.
- Tiền VND: `new Intl.NumberFormat('vi-VN').format(amount) + ' ₫'`
- Loading: dùng `q-skeleton animation="pulse"` cho cả section, không skeleton từng phần tử nhỏ.
- Màu/font lấy từ biến trong `assets/variables.scss`, không hard-code mã màu.
- Polling (cập nhật đơn hàng định kỳ): dùng `composables/createPoller.js`.
- Không commit file `.env`.
- Commit message: `feat:`, `fix:`, `refactor:`.
