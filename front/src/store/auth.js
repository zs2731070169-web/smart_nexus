import { reactive } from 'vue'

const STORAGE_KEY = 'smart_nexus_auth'

const loadStoredAuth = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

const stored = loadStoredAuth()

/** 全局认证状态（响应式） */
export const authStore = reactive({
  token: stored?.token ?? '',
  userPhone: stored?.userPhone ?? '',
  isLoggedIn: !!stored?.token
})

/**
 * 保存登录信息到状态与本地存储
 * @param {string} token - 认证令牌
 * @param {string} userPhone - 手机号
 */
export const saveAuth = (token, userPhone) => {
  authStore.token = token
  authStore.userPhone = userPhone
  authStore.isLoggedIn = true
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, userPhone }))
  // 每次重新登录都从新对话开始，用 sessionStorage 标记（刷新不会触发）
  localStorage.removeItem('smart_nexus_active_session')
  localStorage.removeItem('smart_nexus_local_sessions')
  sessionStorage.setItem('smart_nexus_just_logged_in', '1')
}

/** 清除登录信息 */
export const clearAuth = () => {
  authStore.token = ''
  authStore.userPhone = ''
  authStore.isLoggedIn = false
  localStorage.removeItem(STORAGE_KEY)
}
