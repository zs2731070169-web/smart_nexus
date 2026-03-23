import { CONSULTANT_BASE } from '../config/api'
import { authStore } from '../store/auth'

/** 构造请求 Headers，自动附加 Authorization */
const buildHeaders = (extra = {}) => {
  const headers = { 'Content-Type': 'application/json', ...extra }
  if (authStore.token) {
    headers['Authorization'] = `Bearer ${authStore.token}`
  }
  return headers
}

/**
 * 获取手机验证码
 * @param {string} userPhone
 */
export const getVerificationCode = async (userPhone) => {
  const res = await fetch(`${CONSULTANT_BASE}/code`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ user_phone: userPhone })
  })
  return res.json()
}

/**
 * 用户登录
 * @param {string} userPhone
 * @param {string} code
 */
export const userLogin = async (userPhone, code) => {
  const res = await fetch(`${CONSULTANT_BASE}/login`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ user_phone: userPhone, code })
  })
  return res.json()
}

/** 退出登录 */
export const userLogout = async () => {
  const res = await fetch(`${CONSULTANT_BASE}/logout`, {
    method: 'DELETE',
    headers: buildHeaders()
  })
  return res.json()
}

/** 查询历史会话列表 */
export const queryChatHistory = async () => {
  const res = await fetch(`${CONSULTANT_BASE}/query_chat_history`, {
    method: 'POST',
    headers: buildHeaders()
  })
  return res.json()
}

/**
 * 流式对话（Server-Sent Events）
 * @param {string} query - 用户问题
 * @param {string} sessionId - 会话 ID（前端生成）
 * @yields {Object} StreamMessages 数据帧
 */
export async function* streamChat(query, sessionId) {
  const res = await fetch(`${CONSULTANT_BASE}/chat`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ query, session_id: sessionId })
  })

  if (!res.ok) {
    throw new Error(`请求失败：HTTP ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() // 保留未完成行，等待下一帧

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const payload = line.slice(6).trim()
      if (!payload) continue
      try {
        yield JSON.parse(payload)
      } catch {
        // 忽略无效数据帧
      }
    }
  }
}
