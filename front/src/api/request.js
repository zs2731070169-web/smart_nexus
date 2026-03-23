import axios from 'axios'
import { KNOWLEDGE_BASE } from '../config/api'

// 创建 axios 实例，baseURL 由 config/api.js 统一管理（dev代理 / Electron直连）
const request = axios.create({
  baseURL: KNOWLEDGE_BASE,
  timeout: 120000 // 知识库检索可能较慢，设置 2 分钟超时
})

// 响应拦截器：处理网络层异常
request.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请稍后重试')
    } else if (!error.response) {
      ElMessage.error('网络连接失败，请检查服务是否启动')
    } else {
      ElMessage.error('服务器异常，请稍后重试')
    }
    return Promise.reject(error)
  }
)

export default request
