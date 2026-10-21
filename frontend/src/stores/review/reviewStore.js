import { defineStore } from "pinia";
import apiReviews from "@/apis/reviews/apiReviews";

export const useReviewStore = defineStore("reviewStore", {
    state() {
        return {
            // draft being composed on the review screen
            overallRating: 0,
            overallComment: '',
            itemDrafts: {},     // { [food_item_id]: { rating, comment } }
            submitting: false,

            // what the server already has for the order being viewed.
            // reviewedOrderId says WHICH order the two fields below describe — this
            // store is a singleton, so without it a reviewed order leaves its state
            // behind and the next order renders it for a frame.
            reviewedOrderId: null,
            orderReviewed: false,
            orderOverallRating: null,
            checking: false,

            // public review list on the food detail screen
            foodReviews: [],
            foodReviewsFoodItemId: null,
            loadingFoodReviews: false,
        }
    },

    getters: {
        canSubmit(state) {
            // Overall is the only required field — dish ratings stay optional.
            return state.overallRating > 0 && !state.submitting
        },

        // Only dishes the buyer actually rated become rows; a comment without a
        // star is dropped, because the DB has no rating to store it against.
        ratedItems(state) {
            return Object.entries(state.itemDrafts)
                .filter(([, draft]) => draft.rating > 0)
                .map(([foodItemId, draft]) => ({
                    food_item_id: foodItemId,
                    rating: draft.rating,
                    comment: draft.comment?.trim() || null,
                }))
        }
    },

    actions: {
        resetDraft() {
            this.overallRating = 0
            this.overallComment = ''
            this.itemDrafts = {}
            this.submitting = false
        },

        setItemRating(foodItemId, rating) {
            const draft = this.itemDrafts[foodItemId] || { rating: 0, comment: '' }
            this.itemDrafts[foodItemId] = { ...draft, rating }
        },

        setItemComment(foodItemId, comment) {
            const draft = this.itemDrafts[foodItemId] || { rating: 0, comment: '' }
            this.itemDrafts[foodItemId] = { ...draft, comment }
        },

        async getFoodReviews(foodItemId) {
            try {
                this.loadingFoodReviews = true
                this.foodReviews = []
                this.foodReviewsFoodItemId = null
                const res = await apiReviews.getFoodItemReviews(foodItemId)
                if (res?.data?.success) {
                    this.foodReviews = res.data.reviews
                    this.foodReviewsFoodItemId = foodItemId
                }
            } catch (e) {
                console.error(`reviewStore - getFoodReviews - ${e}`)
                this.foodReviews = []
            } finally {
                this.loadingFoodReviews = false
            }
        },

        async checkOrderReview(orderId) {
            try {
                this.checking = true
                this.reviewedOrderId = null
                const res = await apiReviews.getOrderReview(orderId)
                if (res?.data?.success) {
                    this.orderReviewed = res.data.reviewed
                    this.orderOverallRating = res.data.overall_rating
                    this.reviewedOrderId = orderId
                }
            } catch (e) {
                console.error(`reviewStore - checkOrderReview - ${e}`)
                this.orderReviewed = false
                this.orderOverallRating = null
            } finally {
                this.checking = false
            }
        },

        async submitReview(orderId) {
            try {
                this.submitting = true
                const res = await apiReviews.createReview(orderId, this.overallRating, this.overallComment.trim() || null, this.ratedItems)
                if (res?.data?.success) {
                    this.orderReviewed = true
                    this.orderOverallRating = this.overallRating
                    this.reviewedOrderId = orderId
                    return true
                }
                return false
            } catch (e) {
                console.error(`reviewStore - submitReview - ${e}`)
                throw e
            } finally {
                this.submitting = false
            }
        },
    }
})
