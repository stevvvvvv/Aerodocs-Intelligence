import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // GitHub Pages sert le site sous /<nom-du-dépôt>/ : VITE_BASE est fixé par le workflow
  base: process.env.VITE_BASE ?? "/",
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
