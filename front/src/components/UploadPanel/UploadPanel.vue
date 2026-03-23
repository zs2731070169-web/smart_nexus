<script setup>
import { ref } from 'vue'
import { FolderAdd, UploadFilled, Loading, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { uploadFile } from '../../api/knowledge'

const uploading = ref(false)
const uploadResult = ref(null)

const beforeUpload = (file) => {
  const allowedTypes = ['.md', '.txt']
  const ext = (file.name || '').substring((file.name || '').lastIndexOf('.')).toLowerCase()

  if (!allowedTypes.includes(ext)) {
    ElMessage.warning('仅支持上传 .md 或 .txt 格式的文件')
    return false
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('文件大小不能超过 10MB')
    return false
  }
  return true
}

const handleUpload = async (options) => {
  uploading.value = true
  uploadResult.value = null
  try {
    const res = await uploadFile(options.file)
    if (res.status === '200') {
      uploadResult.value = {
        success: true,
        message: `「${res.filename}」上传成功，已拆分为 ${res.chunk_size} 个知识片段`
      }
      ElMessage.success('知识库上传成功')
    } else {
      uploadResult.value = { success: false, message: res.description || '上传失败，请重试' }
      ElMessage.error(res.description || '上传失败')
    }
  } catch {
    uploadResult.value = { success: false, message: '上传失败，请检查网络连接或服务状态' }
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="upload-panel">
    <h3 class="panel-title">
      <el-icon><FolderAdd /></el-icon>
      <span>知识库上传</span>
    </h3>
    <p class="panel-desc">上传文档到知识库，支持 .md、.txt 格式</p>

    <el-upload
      class="upload-area"
      drag
      action=""
      :http-request="handleUpload"
      :before-upload="beforeUpload"
      :show-file-list="false"
      :disabled="uploading"
      accept=".md,.txt"
    >
      <div class="upload-content">
        <el-icon v-if="!uploading" class="upload-icon"><UploadFilled /></el-icon>
        <el-icon v-else class="upload-icon uploading"><Loading /></el-icon>
        <p class="upload-text">
          {{ uploading ? '正在上传处理中...' : '将文件拖到此处，或点击上传' }}
        </p>
        <p class="upload-hint">仅支持 .md / .txt 文件</p>
      </div>
    </el-upload>

    <!-- 上传结果提示 -->
    <div v-if="uploadResult" class="upload-result" :class="uploadResult.success ? 'success' : 'error'">
      <el-icon v-if="uploadResult.success"><CircleCheck /></el-icon>
      <el-icon v-else><CircleClose /></el-icon>
      <span>{{ uploadResult.message }}</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
$primary: #409eff;

.upload-panel {
  color: #fff;

  .panel-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 500;
    color: $primary;
    margin-bottom: 8px;
  }

  .panel-desc {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.45);
    margin-bottom: 16px;
  }

  // 上传区域
  .upload-area {
    width: 100%;

    :deep(.el-upload) {
      width: 100%;
    }

    :deep(.el-upload-dragger) {
      width: 100%;
      background: rgba(255, 255, 255, 0.04);
      border: 1px dashed rgba(255, 255, 255, 0.2);
      border-radius: 8px;
      padding: 28px 16px;
      transition: all 0.3s;

      &:hover {
        border-color: $primary;
        background: rgba(64, 158, 255, 0.06);
      }
    }

    .upload-content {
      text-align: center;

      .upload-icon {
        font-size: 36px;
        color: $primary;
        margin-bottom: 10px;

        &.uploading {
          animation: spin 1.2s linear infinite;
        }
      }

      .upload-text {
        font-size: 13px;
        color: rgba(255, 255, 255, 0.75);
        margin-bottom: 4px;
      }

      .upload-hint {
        font-size: 12px;
        color: rgba(255, 255, 255, 0.35);
      }
    }
  }

  // 上传结果
  .upload-result {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    margin-top: 14px;
    padding: 10px 12px;
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.5;
    word-break: break-all;

    .el-icon {
      margin-top: 2px;
      flex-shrink: 0;
    }

    &.success {
      background: rgba(103, 194, 58, 0.12);
      color: #95d475;
    }

    &.error {
      background: rgba(245, 108, 108, 0.12);
      color: #f89898;
    }
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
