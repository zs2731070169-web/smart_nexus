<template>
  <div class="chat-page">
    <!-- 左侧会话边栏 -->
    <SessionSidebar
      :sessions="sessions"
      :active-session-id="activeSessionId"
      :user-phone="authStore.userPhone"
      @new-session="createNewSession"
      @select-session="switchSession"
      @open-upload="isUploadOpen = true"
    />

    <!-- 右侧对话窗口（v-show 保持组件挂载，防止切换时丢失进行中的对话状态） -->
    <ChatWindow
      v-for="session in sessions"
      v-show="session.id === activeSessionId"
      :key="session.id"
      :session-id="session.id"
      :session-title="session.title"
      :preloaded-messages="session.preloadedMessages"
      @session-named="updateSessionTitle"
      @logout="handleLogout"
    />

    <!-- 知识库管理抽屉 -->
    <el-drawer
      v-model="isUploadOpen"
      title="知识库文档管理"
      direction="rtl"
      size="380px"
    >
      <UploadPanel />
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { authStore, clearAuth } from '../../store/auth'
import { userLogout, queryChatHistory } from '../../api/consultant'
import SessionSidebar from './SessionSidebar.vue'
import ChatWindow from './ChatWindow.vue'
import UploadPanel from '../UploadPanel/UploadPanel.vue'

// ===== 本地会话持久化（用户手动新建、尚未保存到后端的会话） =====
const LOCAL_SESSIONS_KEY = 'smart_nexus_local_sessions'
const ACTIVE_SESSION_KEY = 'smart_nexus_active_session'

const readLocalSessions = () => {
  try { return JSON.parse(localStorage.getItem(LOCAL_SESSIONS_KEY) || '[]') }
  catch { return [] }
}
const writeLocalSessions = (list) => {
  localStorage.setItem(LOCAL_SESSIONS_KEY, JSON.stringify(list))
}

// ===== 会话工厂 =====
const createSession = (id = crypto.randomUUID(), title = '新对话', preloadedMessages = null) => {
  return { id, title, preloadedMessages }
}

const initialSession = createSession()
const sessions = ref([initialSession])
const activeSessionId = ref(initialSession.id)
const isUploadOpen = ref(false)

// ===== 会话操作 =====
const createNewSession = () => {
  const session = createSession()
  sessions.value.unshift(session)
  activeSessionId.value = session.id
  // 持久化到本地，刷新后可恢复
  const locals = readLocalSessions()
  locals.unshift({ id: session.id, title: '新对话' })
  writeLocalSessions(locals)
}

const switchSession = (sessionId) => {
  activeSessionId.value = sessionId
}

// activeSessionId 变化时持久化
watch(activeSessionId, (id) => {
  localStorage.setItem(ACTIVE_SESSION_KEY, id)
})

const updateSessionTitle = (title) => {
  const session = sessions.value.find(s => s.id === activeSessionId.value)
  if (session && session.title === '新对话') {
    session.title = title
    // 同步更新本地会话列表中的标题
    const locals = readLocalSessions()
    const found = locals.find(s => s.id === session.id)
    if (found) {
      found.title = title
      writeLocalSessions(locals)
    }
  }
}

// ===== 历史消息转换 =====
const convertHistoryMessages = (historyList) =>
  historyList.map((msg, i) => {
    if (msg.role === 'user') {
      return { id: `h${i}`, role: 'user', content: msg.content }
    }
    return {
      id: `h${i}`,
      role: 'assistant',
      thinking: '',
      processing: '',
      answer: msg.content,
      isStreaming: false,
      thinkingExpanded: false
    }
  })

// ===== 启动时加载历史 =====
const loadHistoryOnStart = async () => {
  const justLoggedIn = !!sessionStorage.getItem('smart_nexus_just_logged_in')
  sessionStorage.removeItem('smart_nexus_just_logged_in')

  try {
    const res = await queryChatHistory()
    if (res.status !== '200') return

    const historyItems = res.chat_history_list ?? []
    const historySessions = historyItems.map(item => {
      const historyList = item.history_list ?? []
      const firstUser = historyList.find(m => m.role === 'user')
      const title = firstUser ? firstUser.content.slice(0, 20) : '历史对话'
      return createSession(item.session_id, title, convertHistoryMessages(historyList))
    })

    if (justLoggedIn) {
      // 刚登录：把 initialSession 写入本地会话，确保刷新后仍保留
      writeLocalSessions([{ id: initialSession.id, title: initialSession.title }])
      sessions.value = [initialSession, ...historySessions]
      activeSessionId.value = initialSession.id
      return
    }

    // 刷新：加载本地保存的新建会话，过滤掉已保存到后端的（避免重复）
    const historyIds = new Set(historySessions.map(s => s.id))
    const localStubs = readLocalSessions().filter(s => !historyIds.has(s.id))
    writeLocalSessions(localStubs)
    const localSessions = localStubs.map(s => createSession(s.id, s.title, null))

    // 全部会话 = 本地新建 + 历史
    const allSessions = [...localSessions, ...historySessions]
    if (allSessions.length === 0) return // 无任何会话，保持 initialSession

    const savedId = localStorage.getItem(ACTIVE_SESSION_KEY)
    const savedExists = savedId && allSessions.some(s => s.id === savedId)

    if (savedExists) {
      // 上次停留在某个已知会话 → 直接恢复
      sessions.value = allSessions
      activeSessionId.value = savedId
    } else if (localSessions.length > 0) {
      // savedId 未记录（watch 未触发），但本地会话存在 → 激活第一个本地会话，不额外插入新对话
      sessions.value = allSessions
      activeSessionId.value = localSessions[0].id
    } else {
      // 无任何本地会话，上次在 initialSession → 保留新对话
      sessions.value = [initialSession, ...allSessions]
      activeSessionId.value = initialSession.id
    }
  } catch {
    // 加载失败保持 initialSession
  }
}

// ===== 退出登录 =====
const handleLogout = async () => {
  try {
    await userLogout()
  } finally {
    clearAuth()
  }
}

onMounted(() => {
  loadHistoryOnStart()
})
</script>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
  overflow: hidden;
}
</style>
