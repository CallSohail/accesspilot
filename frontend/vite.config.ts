import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The app talks to the AccessPilot backend. In dev, /api requests are proxied
// to http://localhost:8000 (no CORS pain). Direct calls to the backend URL
// also work because 5173 is in the backend CORS allow-list.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
