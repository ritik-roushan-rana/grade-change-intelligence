import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    // The API runs on 8000. Requests go through this proxy in dev, so the app
    // talks to a same-origin /api path and CORS never enters the picture during
    // a demo. The backend also sends CORS headers for Vite's origin, so a build
    // served from elsewhere can point at the API directly via VITE_API_BASE_URL.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
