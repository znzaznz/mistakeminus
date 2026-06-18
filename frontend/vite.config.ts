import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 本地单用户：前端 5173，把 /api 代理到后端 8000，避免硬编码后端地址
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      // 题目配图：后端 StaticFiles 挂在 /media
      "/media": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
