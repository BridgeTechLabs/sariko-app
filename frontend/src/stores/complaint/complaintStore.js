import { defineStore } from "pinia";
import apiComplaints from "@/apis/complaints/apiComplaints";
import { fileToBase64 } from "@/utils/fileToBase64";

// T35: complaints tied to an order. Limits (window, photos, length) come from GET /complaints/config.
export const useComplaintStore = defineStore("complaintStore", {
    state() {
        return {
            config: null,           // { window_hours, max_images, max_file_mb, max_length, categories: {buyer, seller} }
            mine: [],
            loadingMine: false,
            detail: null,           // the complaint on the detail screen, with signed image URLs
            loadingDetail: false,

            // form
            category: '',
            description: '',
            files: [],
            submitting: false,
            error: null,            // { code, params } of the last failed submit
            created: null,          // { id, code, imagesFailed } once sent
        }
    },

    actions: {
        async loadConfig() {
            if (this.config) return
            try {
                this.config = await apiComplaints.getConfig()
            } catch (e) {
                console.error(`complaintStore - loadConfig - ${e}`)
            }
        },

        async loadMine() {
            this.loadingMine = true
            try {
                this.mine = (await apiComplaints.getMine()).complaints || []
            } catch (e) {
                console.error(`complaintStore - loadMine - ${e}`)
            } finally {
                this.loadingMine = false
            }
        },

        async loadDetail(complaintId) {
            this.loadingDetail = true
            this.detail = null
            try {
                this.detail = (await apiComplaints.getDetail(complaintId)).complaint
            } catch (e) {
                console.error(`complaintStore - loadDetail - ${e}`)
            } finally {
                this.loadingDetail = false
            }
        },

        resetForm() {
            this.category = ''
            this.description = ''
            this.files = []
            this.submitting = false
            this.error = null
            this.created = null
        },

        // The complaint first (it gets its code), then one request per photo: nginx caps a request
        // at 10 MB. A photo that fails does not undo the complaint; the screen says how many failed.
        async submit(orderId) {
            this.submitting = true
            this.error = null
            try {
                const { complaint } = await apiComplaints.create(orderId, this.category, this.description.trim())
                let imagesFailed = 0
                for (const file of this.files) {
                    try {
                        await apiComplaints.uploadImage(complaint.id, await fileToBase64(file))
                    } catch (e) {
                        console.error(`complaintStore - uploadImage - ${e}`)
                        imagesFailed += 1
                    }
                }
                this.created = { id: complaint.id, code: complaint.code, imagesFailed }
            } catch (e) {
                this.error = { code: e.code, params: e.params }
            } finally {
                this.submitting = false
            }
        },
    },
})

export default useComplaintStore
