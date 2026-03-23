import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_KEY = 'smart_nexus_auth'

const loadStoredAuth = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const stored = loadStoredAuth()

  const token = ref(stored?.token ?? '')
  const userPhone = ref(stored?.userPhone ?? '')
  const isLoggedIn = computed(() => !!token.value)

  /**
   * 保存登录信息到状态与本地存储
   * @param {string} newToken - 认证令牌
   * @param {string} phone - 手机号
   */
  const saveAuth = (newToken, phone) => {
    token.value = newToken
    userPhone.value = phone
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: newToken, userPhone: phone }))
    // 每次重新登录都从新对话开始，用 sessionStorage 标记（刷新不会触发）
    localStorage.removeItem('smart_nexus_active_session')
    localStorage.removeItem('smart_nexus_local_sessions')
    sessionStorage.setItem('smart_nexus_just_logged_in', '1')
  }

  /** 清除登录信息 */
  const clearAuth = () => {
    token.value = ''
    userPhone.value = ''
    localStorage.removeItem(STORAGE_KEY)
  }

  return { token, userPhone, isLoggedIn, saveAuth, clearAuth }
})
