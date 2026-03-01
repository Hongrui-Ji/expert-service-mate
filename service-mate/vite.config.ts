import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/workspace/schedule/', // <--- 关键：设置基础路径，确保资源(js/css)在子路径下能加载
  server: {
    port: 5173, // 开发端口
  }
})