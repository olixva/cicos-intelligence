import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// Vite config — SPA estática servida por el mismo reverse-proxy que el backend
// en producción. `VITE_API_BASE_URL=""` significa que las
// llamadas del frontend van a same-origin.
//
// En dev, vite sirve el frontend en :5173 mientras el backend uvicorn vive
// en :8000. Para mantener `baseUrl: ""` y same-origin en el código del
// cliente, configuramos `server.proxy` que redirige las llamadas al backend
// hacia :8000 sin que el código de la app se entere. El proxy SOLO aplica
// a `vite dev`; `vite build` y `vite preview` no lo usan (producción queda
// detrás del reverse-proxy real).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
      '/api/v1': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    target: 'es2022',
  },
});
