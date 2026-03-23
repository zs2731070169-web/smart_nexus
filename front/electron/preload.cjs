// preload.cjs - contextIsolation 模式下的预加载脚本
const { contextBridge, ipcRenderer } = require('electron')

// 向渲染进程暴露窗口控制 API
contextBridge.exposeInMainWorld('electronAPI', {
  version: process.versions.electron,
  minimize: () => ipcRenderer.invoke('win:minimize'),
  maximize: () => ipcRenderer.invoke('win:maximize'),
  close: () => ipcRenderer.invoke('win:close'),
  isMaximized: () => ipcRenderer.invoke('win:is-maximized'),
  // 监听最大化状态变更（返回取消监听函数）
  onMaximizeChange: (callback) => {
    const handler = (_, isMax) => callback(isMax)
    ipcRenderer.on('win:maximize-change', handler)
    return () => ipcRenderer.off('win:maximize-change', handler)
  }
})
