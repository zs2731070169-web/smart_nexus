import {knowledgeRequest as request} from './request'

/**
 * 上传文件到知识库
 * @param {File} file - 要上传的文件对象
 * @returns {Promise} 上传结果
 */
export const uploadFile = (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/injection/upload', formData, {
        headers: {'Content-Type': 'multipart/form-data'}
    })
}
