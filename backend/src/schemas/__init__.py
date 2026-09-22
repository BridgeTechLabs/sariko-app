"""Request schemas, one class per module.

Dùng qua namespace `Schema` để chỗ gọi không phải liệt kê từng import:

    from schemas import Schema

    def create_order(request: Schema.RequestCreateOrder): ...
"""
from schemas.request_upload_image import RequestUploadImage

# Cart API
from schemas.request_read_cart_items import RequestReadCartItems
from schemas.request_add_cart_item import RequestAddCartItem
from schemas.request_update_cart_item import RequestUpdateCartItem

# Chat API
from schemas.request_create_conversation import RequestCreateConversation
from schemas.request_set_pinned import RequestSetPinned

# User Profile API
from schemas.request_update_profile import RequestUpdateProfile

# Order API
from schemas.request_create_order import RequestCreateOrder

# Review API
from schemas.request_review_item import RequestReviewItem
from schemas.request_create_review import RequestCreateReview

# Seller Order API
from schemas.request_update_order_status import RequestUpdateOrderStatus

# Seller Menu — Categories
from schemas.request_create_category import RequestCreateCategory
from schemas.request_update_category import RequestUpdateCategory

# Seller Menu — Food Items
from schemas.request_create_food_item import RequestCreateFoodItem
from schemas.request_update_food_item import RequestUpdateFoodItem

# Deliveries
from schemas.request_quotation import RequestQuotation


class Schema:
    RequestUploadImage = RequestUploadImage

    RequestReadCartItems = RequestReadCartItems
    RequestAddCartItem = RequestAddCartItem
    RequestUpdateCartItem = RequestUpdateCartItem

    RequestCreateConversation = RequestCreateConversation
    RequestSetPinned = RequestSetPinned

    RequestUpdateProfile = RequestUpdateProfile

    RequestCreateOrder = RequestCreateOrder

    RequestReviewItem = RequestReviewItem
    RequestCreateReview = RequestCreateReview

    RequestUpdateOrderStatus = RequestUpdateOrderStatus

    RequestCreateCategory = RequestCreateCategory
    RequestUpdateCategory = RequestUpdateCategory

    RequestCreateFoodItem = RequestCreateFoodItem
    RequestUpdateFoodItem = RequestUpdateFoodItem

    RequestQuotation = RequestQuotation
