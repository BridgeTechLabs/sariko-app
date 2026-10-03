import { supabase } from '@/lib/supabase.js'

export const apiAuth = {

    authGetSession: async() => {
        const { data, error } = await supabase.auth.getSession();
        if (error) throw new Error("Error in apiGetSession: ", error)
        return data
    },

    authSignin: async(email, password) => {
        const { data, error } = await supabase.auth.signInWithPassword({ email: email, password: password })
        if (error) throw error
        return data
    },

    authSignup: async(email, password, fullname, isSeller) => {
        const { data, error } = await supabase.auth.signUp({
            email,
            password,
            options: {
                data: {
                    fullname: fullname,
                    is_seller: isSeller
                },
            },
        });
        if (error) throw error
        return data
    },
 
    authSignout: async() => {
        const { data, error } = await supabase.auth.signOut()
        if (error) throw error
        return data
    },

    authUpdatePassword: async(password) => {
        const { data, error } = await supabase.auth.updateUser({ password })
        if (error) throw error
        return data
    }
}

export default apiAuth;