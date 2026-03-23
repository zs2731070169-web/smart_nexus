<template>
  <div class="login-page">
    <div class="login-card">
      <!-- 品牌头部 -->
      <div class="login-brand">
        <el-icon class="brand-icon"><Monitor /></el-icon>
        <h1 class="brand-title">Smart Nexus</h1>
        <p class="brand-desc">设备售后智能顾问</p>
      </div>

      <!-- 登录表单 -->
      <el-form class="login-form" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input
            v-model="phone"
            size="large"
            placeholder="请输入手机号"
            maxlength="11"
            :prefix-icon="Phone"
            clearable
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <div class="code-row">
            <el-input
              ref="codeInputRef"
              v-model="code"
              size="large"
              placeholder="请输入验证码"
              maxlength="6"
              :prefix-icon="Key"
              class="code-input"
              @keyup.enter="handleLogin"
            />
            <el-button
              size="large"
              :disabled="!isPhoneValid || countdown > 0"
              :loading="codeLoading"
              class="code-btn"
              @click="handleGetCode"
            >
              {{ countdown > 0 ? `${countdown}s 后重试` : '获取验证码' }}
            </el-button>
          </div>
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          native-type="submit"
          :loading="loginLoading"
          :disabled="!canSubmit"
          class="submit-btn"
        >
          登 录
        </el-button>
      </el-form>

      <p class="security-tip">本系统仅供授权人员使用，请勿共享账号</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { Monitor, Phone, Key } from '@element-plus/icons-vue'
import { getVerificationCode, userLogin } from '../../api/consultant'
import { saveAuth } from '../../store/auth'

const PHONE_REGEX = /^1[3-9]\d{9}$/
const CODE_COUNTDOWN_SECONDS = 60

const phone = ref('')
const code = ref('')
const countdown = ref(0)
const codeLoading = ref(false)
const loginLoading = ref(false)
const codeInputRef = ref(null)
let countdownTimer = null

const isPhoneValid = computed(() => PHONE_REGEX.test(phone.value))
const canSubmit = computed(() => isPhoneValid.value && code.value.length >= 4)

const handleGetCode = async () => {
  if (!isPhoneValid.value || codeLoading.value || countdown.value > 0) return
  codeLoading.value = true
  try {
    const res = await getVerificationCode(phone.value)
    if (res.status === '200') {
      if (res.code) code.value = res.code
      ElMessage.success('验证码已发送，请注意查收')
      startCountdown()
      // 回填后将焦点移到验证码输入框，使回车可直接登录
      nextTick(() => codeInputRef.value?.focus())
    } else {
      ElMessage.error(res.message || '获取验证码失败，请稍后重试')
    }
  } catch {
    ElMessage.error('网络异常，请检查服务是否可用')
  } finally {
    codeLoading.value = false
  }
}

const startCountdown = () => {
  countdown.value = CODE_COUNTDOWN_SECONDS
  countdownTimer = setInterval(() => {
    if (--countdown.value <= 0) clearInterval(countdownTimer)
  }, 1000)
}

const handleLogin = async () => {
  if (!canSubmit.value || loginLoading.value) return
  loginLoading.value = true
  try {
    const res = await userLogin(phone.value, code.value)
    if (res.status === '200' && res.auth_token) {
      saveAuth(res.auth_token, phone.value)
    } else {
      ElMessage.error(res.message || '登录失败，请检查验证码是否正确')
    }
  } catch {
    ElMessage.error('网络异常，请检查服务是否可用')
  } finally {
    loginLoading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f0fb 0%, #f0f4f8 50%, #e8f0fb 100%);
}

.login-card {
  width: 420px;
  padding: 48px 40px 40px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(64, 100, 180, 0.12);
  border: 1px solid #dde1e7;
}

.login-brand {
  text-align: center;
  margin-bottom: 36px;
}

.brand-icon {
  font-size: 52px;
  color: #409eff;
  margin-bottom: 12px;
}

.brand-title {
  font-size: 28px;
  font-weight: 700;
  color: #1a2a44;
  letter-spacing: 1px;
  margin-bottom: 6px;
}

.brand-desc {
  font-size: 14px;
  color: #909399;
}

.login-form {
  margin-bottom: 8px;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.code-row {
  display: flex;
  gap: 10px;
  width: 100%;
}

.code-input {
  flex: 1;
}

.code-btn {
  flex-shrink: 0;
  min-width: 120px;
}

.submit-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  letter-spacing: 2px;
  border-radius: 8px;
  margin-top: 4px;
}

.security-tip {
  text-align: center;
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 20px;
}
</style>
