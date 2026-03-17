<template>
  <div class="chat-panel">
    <!-- 顶部标题栏 -->
    <div class="chat-header">
      <el-icon><ChatDotRound /></el-icon>
      <span>智能知识检索</span>
    </div>

    <!-- 消息列表 -->
    <div class="chat-messages" ref="messagesContainer">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="message-row"
        :class="msg.role"
      >
        <!-- 头像 -->
        <div class="message-avatar">
          <el-icon v-if="msg.role === 'assistant'"><Service /></el-icon>
          <el-icon v-else><User /></el-icon>
        </div>
        <!-- 消息气泡 -->
        <div class="message-bubble">
          <div
            v-if="msg.role === 'assistant'"
            class="message-content markdown-body"
            v-html="renderMarkdown(msg.content)"
          ></div>
          <div v-else class="message-content">{{ msg.content }}</div>
        </div>
      </div>

      <!-- 加载中提示 -->
      <div v-if="loading" class="message-row assistant">
        <div class="message-avatar">
          <el-icon><Service /></el-icon>
        </div>
        <div class="message-bubble">
          <div class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="chat-input-area">
      <div class="input-wrapper">
        <el-input
          v-model="inputText"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 4 }"
          placeholder="输入您的问题，例如：电脑蓝屏怎么解决？"
          resize="none"
          @keydown.enter.exact.prevent="sendMessage"
          :disabled="loading"
        />
        <el-button
          class="send-btn"
          type="primary"
          :icon="Promotion"
          :disabled="!inputText.trim() || loading"
          @click="sendMessage"
        >
          发送
        </el-button>
      </div>
      <p class="input-hint">按 Enter 发送，Shift + Enter 换行</p>
    </div>
  </div>
</template>

<script>
import { ref, nextTick } from 'vue'
import {ChatDotRound, Promotion, Service, User} from '@element-plus/icons-vue'
import { marked } from 'marked'
import { queryKnowledge } from '../../api/knowledge'

// 图片扩展名匹配
const IMAGE_URL_RE = /\.(png|jpe?g|gif|webp|svg|bmp|ico)(\?[^\s)]*)?$/i

// 自定义渲染器：将图片链接渲染为 <img>
const renderer = {
  link({ href, title, text }) {
    if (href && IMAGE_URL_RE.test(href)) {
      const alt = text || title || '图片'
      return `<img src="${href}" alt="${alt}" title="${title || ''}" class="chat-image" />`
    }
    const titleAttr = title ? ` title="${title}"` : ''
    return `<a href="${href}"${titleAttr} target="_blank" rel="noopener">${text}</a>`
  }
}

// 配置 marked
marked.setOptions({ breaks: true, gfm: true })
marked.use({ renderer })

// 生成消息唯一 ID
let messageId = 0
function createMessage(role, content) {
  return {
    id: ++messageId,
    role: role,
    content: content
  }
}

export default {
  name: 'ChatPanel',
  components: {ChatDotRound, User, Service},
  setup() {
    const messagesContainer = ref(null)
    const inputText = ref('')
    const loading = ref(false)

    // 初始欢迎消息
    const messages = ref([
      createMessage(
        'assistant',
        '您好！我是 **Smart Nexus 智能知识顾问**，专注于为您提供电脑售后技术支持。\n\n' +
        '您可以向我提问任何电脑相关的问题，例如：\n' +
        '- 电脑蓝屏怎么处理？\n' +
        '- 怎么升级手机系统？\n' +
        '- 驱动安装失败怎么办？\n\n' +
        '也可以在左侧上传知识文档来扩充知识库。请问有什么可以帮您？'
      )
    ])

    // 渲染 Markdown 为 HTML
    function renderMarkdown(content) {
      if (!content) return ''
      return marked.parse(content)
    }

    // 滚动到底部
    function scrollToBottom() {
      nextTick(() => {
        const container = messagesContainer.value
        if (container) {
          container.scrollTop = container.scrollHeight
        }
      })
    }

    // 发送消息
    async function sendMessage() {
      const question = inputText.value.trim()
      if (!question || loading.value) return

      // 添加用户消息
      messages.value.push(createMessage('user', question))
      inputText.value = ''
      loading.value = true
      scrollToBottom()

      try {
        const res = await queryKnowledge(question)

        if (res.status === '200') {
          const answer = res.content || '抱歉，未检索到相关知识，请尝试换个问法。'
          messages.value.push(createMessage('assistant', answer))
        } else {
          const errorMsg = res.description || '查询失败，请稍后重试'
          messages.value.push(
            createMessage('assistant', `抱歉，查询遇到了问题：${errorMsg}`)
          )
        }
      } catch (err) {
        messages.value.push(
          createMessage('assistant', '抱歉，服务暂时无法连接，请检查后端服务是否正常运行，稍后再试。')
        )
      } finally {
        loading.value = false
        scrollToBottom()
      }
    }

    return {
      messagesContainer,
      inputText,
      messages,
      loading,
      renderMarkdown,
      sendMessage,
      Promotion
    }
  }
}
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* ========== 顶部栏 ========== */
.chat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 24px;
  font-size: 16px;
  font-weight: 600;
  color: #1a2a44;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.chat-header .el-icon {
  font-size: 20px;
  color: #409eff;
}

/* ========== 消息区域 ========== */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 24px 12px;
}

/* 单条消息行 */
.message-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 80%;
}

.message-row.user {
  flex-direction: row-reverse;
  margin-left: auto;
}

/* 头像 */
.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
}

.message-row.assistant .message-avatar {
  background: #409eff;
  color: #fff;
}

.message-row.user .message-avatar {
  background: #1a2a44;
  color: #fff;
}

/* 气泡 */
.message-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 14px;
  word-break: break-word;
}

.message-row.assistant .message-bubble {
  background: #fff;
  color: #303133;
  border-top-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.message-row.user .message-bubble {
  background: #409eff;
  color: #fff;
  border-top-right-radius: 4px;
}

/* ========== Markdown 内容样式 ========== */
.markdown-body :deep(p) {
  margin: 0 0 8px 0;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 4px 0 8px 0;
  padding-left: 20px;
}

.markdown-body :deep(li) {
  margin-bottom: 2px;
}

.markdown-body :deep(strong) {
  font-weight: 600;
}

.markdown-body :deep(code) {
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: #c7254e;
}

.markdown-body :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}

.markdown-body :deep(pre code) {
  background: none;
  color: inherit;
  padding: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 12px 0 6px 0;
  font-weight: 600;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid #409eff;
  padding-left: 12px;
  color: #606266;
  margin: 8px 0;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e4e7ed;
  padding: 6px 10px;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #f5f7fa;
  font-weight: 600;
}

/* 图片样式 */
.markdown-body :deep(.chat-image) {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  margin: 8px 0;
  cursor: pointer;
  transition: opacity 0.2s;
  display: block;
}

.markdown-body :deep(.chat-image:hover) {
  opacity: 0.9;
}

/* ========== 打字指示器 ========== */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #409eff;
  animation: typing 1.4s ease-in-out infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  30% {
    opacity: 1;
    transform: scale(1);
  }
}

/* ========== 输入区域 ========== */
.chat-input-area {
  padding: 16px 24px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-wrapper :deep(.el-textarea__inner) {
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.5;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.send-btn {
  height: 40px;
  border-radius: 8px;
  flex-shrink: 0;
}

.input-hint {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 6px;
  text-align: right;
}
</style>
