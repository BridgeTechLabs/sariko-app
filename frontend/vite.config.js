import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import { quasar, transformAssetUrls } from '@quasar/vite-plugin'

export default defineConfig({
    build: {
        target: 'es2022',  // Changed from es2023 for better compatibility
        commonjsOptions: {
            include: [/@supabase\/supabase-js/, /node_modules/]
        }
    },
    optimizeDeps: {
        include: ['@supabase/supabase-js']
    },
    css: {
        preprocessorOptions: {
            scss: {
                additionalData: `@import "@/assets/variables.scss";`
            }
        }
    },
    plugins: [
        vue({
            template: { transformAssetUrls }
        }),
        quasar({}),

        VitePWA({
            registerType: 'autoUpdate',
            includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'masked-icon.svg'],
            manifest: {
                name: 'Sariko',
                short_name: 'Sariko',
                description: 'Community marketplace for Filipino homemade food and products',
                theme_color: '#FF6B35',
                background_color: '#ffffff',
                display: 'standalone',
                start_url: '/',
                icons: [
                    {
                        src: '/icons/icon-192x192.png',
                        sizes: '192x192',
                        type: 'image/png'
                    },
                    {
                        src: '/icons/icon-512x512.png',
                        sizes: '512x512',
                        type: 'image/png'
                    },
                    {
                        src: '/icons/icon-512x512.png',
                        sizes: '512x512',
                        type: 'image/png',
                        purpose: 'maskable'
                    }
                ]
            },
            workbox: {
                globPatterns: ['**/*.{js,css,html,ico,png,svg,jpg,jpeg,webp}'],
                runtimeCaching: [
                    {
                        urlPattern: /^https:\/\/images\.unsplash\.com\/.*/i,
                        handler: 'CacheFirst',
                        options: {
                            cacheName: 'images-cache',
                            expiration: {
                                maxEntries: 50,
                                maxAgeSeconds: 60 * 60 * 24 * 30
                            }
                        }
                    }
                ]
            }
        })
    ],
    resolve: {
        alias: {
            '@': '/src'
        }
    },
    server: {
        host: '0.0.0.0',
        port: 8081,
        proxy: {
            '/rest': {
                target: 'http://localhost:5000',
                // target: 'http://10.10.1.114:5000',
                // target: 'https://api.sariko.store',
                changeOrigin: true,
            }
        },
        allowedHosts: ['preorbital-mona-magical.ngrok-free.dev']
    }
})
