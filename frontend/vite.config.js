import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
    plugins: [vue()],
    server: {
        host: true, // Listen on all addresses, including LAN and public
        port: 5173,
        watch: {
        usePolling: true // Essential for Docker on Windows/Mac to detect file changes
        }
    }
})