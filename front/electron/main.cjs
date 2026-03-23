const { app, BrowserWindow, session, Menu, dialog, ipcMain } = require('electron')
const path = require('path')

const isDev = !app.isPackaged

// 模块级 win 引用，供 ipcMain 访问
let win = null

/**
 * 为 Electron renderer 注入 CORS 响应头，允许从 file:// 协议访问本地后端
 * 开发模式下通过 Vite dev server 代理，无需此处理
 */
function setupCorsHeaders() {
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Access-Control-Allow-Origin': ['*'],
        'Access-Control-Allow-Headers': ['*'],
        'Access-Control-Allow-Methods': ['GET, POST, PUT, DELETE, OPTIONS']
      }
    })
  })
}

function createWindow() {
  win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    frame: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      // 禁止后台限速，防止窗口切走后 SSE 的 reader.read() await 被严重拖慢
      backgroundThrottling: false
    },
    title: 'Smart Nexus - 设备售后智能顾问',
    show: false
  })

  if (isDev) {
    // 开发模式：加载 Vite dev server（需先运行 npm run dev）
    win.loadURL('http://localhost:3000')
    win.webContents.openDevTools()
  } else {
    // 生产模式：加载构建产物
    setupCorsHeaders()
    win.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  win.once('ready-to-show', () => win.show())

  // 拦截所有关闭请求，弹窗确认防止误操作
  win.on('close', (e) => {
    e.preventDefault()
    dialog.showMessageBox(win, {
      type: 'question',
      buttons: ['退出', '取消'],
      defaultId: 1,
      cancelId: 1,
      title: '退出确认',
      message: '确定要退出 Smart Nexus 吗？'
    }).then(({ response }) => {
      if (response === 0) win.destroy()
    })
  })

  // 通知渲染进程最大化状态变更，用于切换标题栏按钮图标
  win.on('maximize', () => win.webContents.send('win:maximize-change', true))
  win.on('unmaximize', () => win.webContents.send('win:maximize-change', false))

  // 阻止 window.location 跳转触发的导航
  win.webContents.on('will-navigate', (event) => {
    event.preventDefault()
  })

  // 阻止 webContents.reload() 触发的重载（will-navigate 捕获不到此类重载）
  win.webContents.on('will-reload', (event) => {
    event.preventDefault()
  })

  // 阻止 Ctrl+R / F5 键盘刷新
  win.webContents.on('before-input-event', (event, input) => {
    if (input.type !== 'keyDown') return
    if ((input.control && (input.key === 'r' || input.key === 'R')) || input.key === 'F5') {
      event.preventDefault()
    }
  })

  win.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error(`页面加载失败：${errorCode} - ${errorDescription}`)
  })
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null)
  createWindow()

  // 窗口控制 IPC
  ipcMain.handle('win:minimize', () => win.minimize())
  ipcMain.handle('win:maximize', () => {
    if (win.isMaximized()) win.unmaximize()
    else win.maximize()
  })
  ipcMain.handle('win:close', () => win.close())
  ipcMain.handle('win:is-maximized', () => win.isMaximized())
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
