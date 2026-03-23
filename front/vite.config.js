import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())

  return {
    plugins: [
      vue(),
      AutoImport({
        resolvers: [ElementPlusResolver()],
        dts: false
      }),
      Components({
        resolvers: [ElementPlusResolver()],
        dts: false
      })
    ],
    // Electron 打包时需要相对路径，否则 file:// 协议下资源加载失败
    base: './',
    server: {
      port: parseInt(env.VITE_PORT) || 3000,
      proxy: {
        '/api': {
          target: env.VITE_API_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, env.VITE_API_BASE_PATH || '/smart/nexus/knowledge')
        },
        '/consultant': {
          target: env.VITE_CONSULTANT_TARGET || 'http://127.0.0.1:8001',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/consultant/, env.VITE_CONSULTANT_BASE_PATH || '/smart/nexus/consultant')
        }
      }
    }
  }
})
