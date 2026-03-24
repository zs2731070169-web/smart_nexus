import axios from 'axios'
import {KNOWLEDGE_BASE, CONSULTANT_BASE} from '../config/api'
import {useAuthStore} from '../store/auth'

// ===== 知识库服务实例 =====
// 知识库检索可能较慢，设置 2 分钟超时
const knowledgeRequest = axios.create({
    baseURL: KNOWLEDGE_BASE,
    timeout: 120000
})

// 响应拦截器：处理网络层异常
knowledgeRequest.interceptors.response.use(
    (response) => response.data,
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

// ===== 顾问服务实例 =====
const consultantRequest = axios.create({
    baseURL: CONSULTANT_BASE,
    timeout: 1200000
})

// 请求拦截器：自动附加 Authorization
consultantRequest.interceptors.request.use((config) => {
    const authStore = useAuthStore()
    if (authStore.token) {
        config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
})

// 响应拦截器：处理网络层异常
consultantRequest.interceptors.response.use(
    (response) => response.data,
    (error) => {
        if (error.code === 'ECONNABORTED') {
            ElMessage.error('请求超时，请稍后重试')
        } else if (!error.response) {
            ElMessage.error('网络连接失败，请检查服务是否启动')
        } else if (error.response.status === 401) {
            const authStore = useAuthStore()
            authStore.clearAuth()
            ElMessage.warning('登录已过期，请重新登录')
        } else {
            ElMessage.error('服务器异常，请稍后重试')
        }
        return Promise.reject(error)
    }
)

export {knowledgeRequest, consultantRequest}
