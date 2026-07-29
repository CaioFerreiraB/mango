import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    // Em dev a SPA roda no Vite e a API no FastAPI (:8000). O backend já serve a API sob /api,
    // então é só encaminhar — sem reescrever o caminho. Em produção tudo vem da mesma origem.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
})
