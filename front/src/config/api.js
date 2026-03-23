/**
 * API 基础地址配置
 * - 开发模式（http://）：通过 Vite dev server 代理转发
 * - 生产模式（Electron file://）：直连本地后端服务
 */
const isElectronFile = typeof window !== 'undefined' && window.location.protocol === 'file:'

export const CONSULTANT_BASE = isElectronFile
  ? 'http://127.0.0.1:8001/smart/nexus/consultant'
  : '/consultant'

export const KNOWLEDGE_BASE = isElectronFile
  ? 'http://127.0.0.1:8000/smart/nexus/knowledge'
  : '/api'
