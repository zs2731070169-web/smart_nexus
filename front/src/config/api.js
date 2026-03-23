/**
 * API 基础地址配置
 * - 开发模式（http://）：通过 Vite dev server 代理转发
 * - 生产模式（Electron file://）：从 electron/main.cjs 读取的 config.json 获取地址，
 *   无需硬编码，修改服务器 IP/域名只需更新 exe 同目录下的 config.json，不必重新打包
 */
const isElectronFile = typeof window !== 'undefined' && window.location.protocol === 'file:'

// 从 preload 注入的配置中读取，并提供内置默认值兜底
const electronConfig = (typeof window !== 'undefined' && window.electronAPI?.config) || {}

export const CONSULTANT_BASE = isElectronFile
  ? (electronConfig.consultantBase || 'http://127.0.0.1:8001/smart/nexus/consultant')
  : '/consultant'

export const KNOWLEDGE_BASE = isElectronFile
  ? (electronConfig.knowledgeBase || 'http://127.0.0.1:8000/smart/nexus/knowledge')
  : '/api'
