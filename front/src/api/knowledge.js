import request from './request'

/**
 * 上传文件到知识库
 * @param {File} file - 要上传的文件对象
 * @returns {Promise} 上传结果
 */
export function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/injection/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 查询知识库
 * @param {string} question - 查询问题
 * @param {number} topK - 返回条数，0 表示使用默认值
 * @returns {Promise} 查询结果
 */
export function queryKnowledge(question, topK = 0) {
  return request.post('/retrieval/query', {
    question: question,
    top_k: topK
  })
}
