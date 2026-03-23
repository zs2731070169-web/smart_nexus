import axios from 'axios'
import { consultantRequest } from './request'

/**
 * 获取手机验证码
 * @param {string} userPhone
 */
export const getVerificationCode = async (userPhone) => {
  return consultantRequest.post('/code', { user_phone: userPhone })
}

/**
 * 用户登录
 * @param {string} userPhone
 * @param {string} code
 */
export const userLogin = async (userPhone, code) => {
  return consultantRequest.post('/login', { user_phone: userPhone, code })
}

/** 退出登录 */
export const userLogout = async () => {
  return consultantRequest.delete('/logout')
}

/**
 * 删除历史会话
 * @param {string} sessionId - 会话 ID
 */
export const deleteChatHistory = async (sessionId) => {
  return consultantRequest.delete('/delete_chat_history', {
    params: { session_id: sessionId }
  })
}

/** 查询历史会话列表 */
export const queryChatHistory = async () => {
  return consultantRequest.post('/query_chat_history')
}

// 公网 IP 缓存（整个会话只查询一次，失败时降级为空字符串由后端兜底）
let _cachedIpPromise = null

const fetchPublicIp = () => {
  if (!_cachedIpPromise) {
    _cachedIpPromise = axios.get('https://api.ipify.org', { params: { format: 'json' } })
      .then(r => r.data.ip || '')
      .catch(() => '')
  }
  return _cachedIpPromise
}

/**
 * 流式对话（Server-Sent Events）
 * axios 通过 onDownloadProgress 回调读取 XHR responseText 增量实现 SSE 消费。
 * @param {string} query - 用户问题
 * @param {string} sessionId - 会话 ID（前端生成）
 * @yields {Object} StreamMessages 数据帧
 */
export async function* streamChat(query, sessionId) {
  const ip = await fetchPublicIp()

  let processedLength = 0
  const pendingEvents = []
  let streamDone = false
  let notifyNewData = null
  let streamError = null

  const axiosPromise = consultantRequest.post(
    '/chat',
    { query, session_id: sessionId, ip },
    {
      responseType: 'text', // 禁止 axios 尝试 JSON 解析 SSE 流
      onDownloadProgress(evt) {
        const fullText = evt.event.target.responseText
        const newText = fullText.slice(processedLength)
        processedLength = fullText.length

        for (const line of newText.split('\n')) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (!payload) continue
          try {
            pendingEvents.push(JSON.parse(payload))
          } catch { /* 忽略无效数据帧 */ }
        }
        notifyNewData?.()
      }
    }
  )

  axiosPromise
    .then(() => { streamDone = true; notifyNewData?.() })
    .catch((err) => { streamError = err; streamDone = true; notifyNewData?.() })

  while (true) {
    while (pendingEvents.length > 0) {
      yield pendingEvents.shift()
    }
    if (streamDone) {
      // 流结束后再次清空可能残留的事件
      while (pendingEvents.length > 0) {
        yield pendingEvents.shift()
      }
      if (streamError) throw streamError
      break
    }
    await new Promise(resolve => { notifyNewData = resolve })
    notifyNewData = null
  }
}
