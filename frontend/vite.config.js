import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server runs on http://localhost:5173 — which the FastAPI backend's CORS
// middleware already allows. `strictPort` makes startup fail loudly instead of
// silently hopping to another port (which would then be blocked by CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
});
