import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server: 默认把 /v1 /health 代理到本地 8765，让前端用相对路径同源调用；
// 生产部署用 FastAPI 的 StaticFiles mount，也走同源。
const target = process.env.VITE_DEV_PROXY_TARGET || "http://localhost:8765";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": { target, changeOrigin: true },
      "/health": { target, changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-charts": ["recharts"],
          "vendor-flow": ["@xyflow/react"],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
});
