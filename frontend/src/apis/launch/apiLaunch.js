import { apiClient } from "@/lib/axiosPolicy.js"

let launch = null

export const apiLaunch = {

    // { prelaunch, launch_date: "YYYY-MM-DD" | null }, fetched once per page load (the router asks on every
    // navigation). A failed call counts as launched: the coming-soon page is a notice, it must not lock the app.
    get: () => {
        launch ??= apiClient.get('/v1/launch')
            .then(res => res.data)
            .catch(() => ({ prelaunch: false, launch_date: null }))
        return launch
    },
}
