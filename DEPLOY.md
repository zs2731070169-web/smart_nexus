# Smart Nexus 云服务器部署文档

## 架构总览

```
用户电脑（Electron 桌面客户端）
    ↓ HTTP / HTTPS
云服务器
    └── Nginx（80 / 443，反向代理）
          ├── /smart/nexus/knowledge  →  knowledge 容器（:8000，FastAPI）
          └── /smart/nexus/consultant →  consultant 容器（:8001，FastAPI + SSE）
                    ↓ 依赖
                ├── MySQL 容器（:3306）
                └── Redis 容器（:6379）
```

---

## 一、服务器初始化

### 1.1 推荐配置

| 配置项 | 最低要求 | 推荐 |
|--------|---------|------|
| CPU    | 2 核    | 4 核 |
| 内存   | 4 GB   | 8 GB |
| 磁盘   | 40 GB SSD | 80 GB SSD |
| 系统   | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| 带宽   | 3 Mbps | 5 Mbps（SSE 流式响应） |

### 1.2 安装 Docker

> 必须从 Docker 官方源安装，Ubuntu 默认源缺少 `docker-compose-plugin`。

```bash
# 卸载旧版本（如已装过）
sudo apt remove docker docker.io containerd runc -y

# 安装依赖
sudo apt update
sudo apt install -y ca-certificates curl gnupg

# 添加 Docker 官方 GPG 密钥
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 添加 Docker 官方 apt 源
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker + Compose 插件
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 验证安装
docker --version          # Docker version 27.x.x
docker compose version    # Docker Compose version v2.x.x

# 将当前用户加入 docker 组（避免每次 sudo）
sudo usermod -aG docker $USER && newgrp docker
```

### 1.3 开放防火墙端口

**① 云服务商控制台**（阿里云 / 腾讯云 / 华为云）安全组入站规则添加：

| 端口 | 协议 | 用途 |
|------|------|------|
| 22   | TCP  | SSH（一般默认已开） |
| 80   | TCP  | HTTP |
| 443  | TCP  | HTTPS（启用 SSL 时） |

**② 服务器系统防火墙**：

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

---

## 二、上传代码

**方式 A — Git（推荐）：**

```bash
cd /opt
git clone https://github.com/你的仓库/smart_nexus.git
cd smart_nexus
```

**方式 B — scp 直传（本地 Windows 执行）：**

```bash
scp -r F:/projects/smart_nexus root@你的服务器IP:/opt/smart_nexus
```

---

## 三、配置环境变量

> 这是部署最关键的步骤，两个 `.env` 文件均不进 git，需在服务器上手动创建。

### 3.1 knowledge 后端

```bash
cd /opt/smart_nexus/backend/knowledge
cp .env.example .env
nano .env
```

```ini
# LLM 模型（用于知识库问答和向量嵌入）
API_KEY=你的 OpenAI 兼容接口 API Key
BASE_URL=https://api.openai-proxy.org/v1
MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-large

# Lenovo iKnow 爬虫目标地址（一般不需要改）
KNOWLEDGE_BASE_URL=https://iknow.lenovo.com.cn
```

### 3.2 consultant 后端

```bash
cd /opt/smart_nexus/backend/consultant
cp .env.example .env
nano .env
```

```ini
# 阿里百炼 LLM（必填）
AL_BAILIAN_API_KEY=你的阿里百炼 API Key
AL_BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MAIN_MODEL_NAME=qwen3.5-plus
SUB_MODEL_NAME=qwen3.5-flash

# MySQL（MYSQL_HOST 必须填 mysql，容器间通过服务名通信）
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=设置一个强密码（与后续 docker compose 使用同一个，密码中不要包含 $ 符号）
MYSQL_DATABASE=smart_nexus
MYSQL_CHARSET=utf8mb4
MYSQL_CONNECT_TIMEOUT=10
MYSQL_MAX_CONNECTIONS=5

# Redis（固定值，不要改）
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_MAX_CONNECTIONS=10

# MCP 工具（必填）
TAVILY_BASE_URL=https://mcp.tavily.com/mcp
TAVILY_API_KEY=你的 Tavily API Key
BAIDUMAP_BASE_URL=https://mcp.map.baidu.com/mcp
BAIDUMAP_AK=你的百度地图 AK

# 知识库服务地址（固定填容器服务名，不要改）
KNOWLEDGE_BASE_URL=http://knowledge:8000/smart/nexus/knowledge/retrieval/query

# 系统配置（固定值，不要改）
APP_PORT=8001
APP_HOST=0.0.0.0

# 登录鉴权
# 用以下命令生成 SECRET_KEY：
#   python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=把上面命令的输出粘贴到这里
ALGORITHM=HS256
TOKEN_EXPIRE_HOURS=24

# 白名单（固定值，不要改）
WHITE_LIST=["/smart/nexus/consultant/code","/smart/nexus/consultant/login"]
```

---

## 四、启动后端服务

`deploy.sh` 会自动完成：检查依赖 → 读取 MySQL 密码 → 创建数据目录 → 构建并启动所有容器。

```bash
cd /opt/smart_nexus
bash backend/deploy/cmd/deploy.sh
```

脚本从 `consultant/.env` 的 `MYSQL_PASSWORD` 自动读取 MySQL root 密码，无需手动输入。

> **首次部署说明**：MySQL 容器首次启动时会自动执行 `smart_nexus.sql` 初始化数据库，耗时约 1～2 分钟。此期间 consultant 容器会等待 MySQL 健康检查通过后再启动，属正常现象。

**正常完成示例：**

```
============================
 ① 检查环境依赖
============================
[INFO]  Docker：Docker version 24.0.0 ...
[INFO]  Docker Compose：Docker Compose version v2.x.x
[INFO]  Docker 服务运行正常 ✓
...
[INFO]  🚀 Smart Nexus 部署完成！
[INFO]  📡 访问地址：http://你的服务器IP
```

---

## 五、验证后端服务

### 5.1 确认容器全部正常运行

```bash
cd /opt/smart_nexus/backend/deploy/docker
docker compose ps
```

期望 5 个服务全部 `Up`：

```
NAME        STATUS
nginx       Up
knowledge   Up
consultant  Up
mysql       Up
redis       Up
```

### 5.2 验证接口联通性

```bash
# 测试 knowledge 服务（根路径返回 {"detail":"Not Found"} 属正常，说明服务已启动）
curl http://你的服务器IP/smart/nexus/knowledge/retrieval/query \
  -X POST -H "Content-Type: application/json" \
  -d '{"question":"测试","top_k":1}'

# 测试 consultant 获取验证码接口
curl -X POST http://你的服务器IP/smart/nexus/consultant/code \
  -H "Content-Type: application/json" \
  -d '{"user_phone":"13800000000"}'
# 期望返回：{"status":"200",...}
```

### 5.3 出错时查看日志

```bash
cd /opt/smart_nexus/backend/deploy/docker
docker compose logs -f consultant
docker compose logs -f knowledge
docker compose logs -f mysql
```

---

## 六、配置 HTTPS（可选但推荐）

### 6.1 申请 SSL 证书

> 前提：域名 DNS 已解析到服务器 IP，且 80 端口可访问。

```bash
sudo apt install -y certbot

# 暂停 nginx 释放 80 端口
cd /opt/smart_nexus/backend/deploy/docker
docker compose stop nginx

# 申请证书
sudo certbot certonly --standalone -d 你的域名.com

# 重启 nginx
docker compose start nginx
```

### 6.2 挂载证书

```bash
mkdir -p /opt/smart_nexus/backend/deploy/nginx/ssl
sudo cp /etc/letsencrypt/live/你的域名.com/fullchain.pem \
        /opt/smart_nexus/backend/deploy/nginx/ssl/
sudo cp /etc/letsencrypt/live/你的域名.com/privkey.pem \
        /opt/smart_nexus/backend/deploy/nginx/ssl/
```

### 6.3 修改 nginx.conf 启用 HTTPS

编辑 `backend/deploy/nginx/nginx.conf`：

1. **取消注释 HTTP 跳转块**：
```nginx
server {
    listen 80;
    server_name 你的域名.com;
    return 301 https://$host$request_uri;
}
```

2. **将原来的 `listen 80;` 替换为**：
```nginx
listen 443 ssl;
server_name 你的域名.com;
ssl_certificate     /etc/nginx/ssl/fullchain.pem;
ssl_certificate_key /etc/nginx/ssl/privkey.pem;
```

### 6.4 取消 docker-compose.yml 中 SSL 目录的注释

编辑 `backend/deploy/docker/docker-compose.yml`，找到 nginx 服务的 volumes 块，取消注释：

```yaml
volumes:
  - ../nginx/nginx.conf:/etc/nginx/nginx.conf
  - ../nginx/ssl:/etc/nginx/ssl   # ← 取消这行的注释
```

### 6.5 重建并重启 Nginx

> 注意：修改了 `volumes` 配置后必须用 `--force-recreate` 重建容器，单纯 `restart` 不会重新挂载目录。

```bash
cd /opt/smart_nexus/backend/deploy/docker
docker compose up -d --force-recreate nginx
```

### 6.6 设置证书自动续签

```bash
(crontab -l 2>/dev/null; echo "0 3 1 * * certbot renew --quiet && \
  cp /etc/letsencrypt/live/你的域名.com/fullchain.pem /opt/smart_nexus/backend/deploy/nginx/ssl/ && \
  cp /etc/letsencrypt/live/你的域名.com/privkey.pem /opt/smart_nexus/backend/deploy/nginx/ssl/ && \
  docker compose -f /opt/smart_nexus/backend/deploy/docker/docker-compose.yml restart nginx") | crontab -
```

---

## 七、打包前端 Electron 客户端

> 在**本地 Windows 开发机**上执行，不是服务器。

### 7.0 前端 API 配置说明

前端有两套独立的 API 地址配置，用途不同，**不要混淆**：

| 配置文件 | 作用范围 | 说明 |
|----------|---------|------|
| `front/.env` | 仅 `npm run dev`（Vite 开发服务器） | Vite 读取该文件做反向代理，将本地 `/api`、`/consultant` 请求转发到后端；打包产物不包含该文件 |
| `front/config.json` | Electron 生产客户端 | 打包进安装包，运行时由主进程读取并通过 IPC 传给渲染进程；`npm run dev` 不使用此文件 |

因此：
- **测试后端联通性**（`npm run dev`）→ 修改 `front/.env` 中的 `VITE_API_TARGET` / `VITE_CONSULTANT_TARGET`
- **打包 Electron 客户端** → 修改 `front/config.json`

### 7.1 修改 config.json 指向云服务器

编辑 `front/config.json`：

```json
{
  "consultantBase": "http://你的服务器IP/smart/nexus/consultant",
  "knowledgeBase":  "http://你的服务器IP/smart/nexus/knowledge"
}
```

如已配置 HTTPS 则使用 `https://你的域名.com/...`。

### 7.2 打包

```bash
cd front
npm install
npm run electron:build
```

打包完成后，安装包位于 `front/electron-dist/` 目录下（`.exe` 安装程序）。

### 7.3 说明：用户如何切换服务器地址

用户安装完成后，如需更换服务器地址，只需修改**安装目录根目录**下的 `config.json`，无需重新安装客户端。

---

## 八、前后端联通验证

1. 安装并打开 Electron 客户端，进入登录页
2. 输入手机号，点击「获取验证码」，在服务器日志中确认收到请求：
   ```bash
   docker compose logs -f consultant | grep "验证码"
   ```
3. 输入验证码完成登录，进入聊天页面
4. 发送一条消息，观察 SSE 流式响应是否正常（文字逐字出现）

---

## 九、日常运维

```bash
# 工作目录（以下命令均在此目录执行）
cd /opt/smart_nexus/backend/deploy/docker

# 查看所有容器状态
docker compose ps

# 实时查看某服务日志
docker compose logs -f consultant
docker compose logs -f knowledge
docker compose logs -f mysql

# 重启某个服务（配置未变时使用）
docker compose restart consultant

# 重建某个服务（修改了 volumes / 环境变量后使用）
docker compose up -d --force-recreate consultant

# 更新代码后重新部署
cd /opt/smart_nexus && git pull
bash backend/deploy/cmd/deploy.sh

# 停止所有服务
cd /opt/smart_nexus/backend/deploy/docker && docker compose down

# 停止并清除数据卷（⚠️ 数据库数据会丢失）
docker compose down -v
```

---

## 十、常见问题排错

### consultant 启动报 `Connection refused`（MySQL）

MySQL 首次启动需执行初始化 SQL，耗时 1～2 分钟。`deploy.sh` 已配置健康检查，consultant 会自动等待，无需手动干预。若等待超过 3 分钟仍未启动，执行：

```bash
cd /opt/smart_nexus/backend/deploy/docker
docker compose logs mysql   # 查看 MySQL 初始化日志
```

### consultant 报 `Access denied for user 'root'`（MySQL 密码不匹配）

MySQL 数据目录已用旧密码初始化，修改密码后需清空重建：

```bash
cd /opt/smart_nexus/backend/deploy/docker
docker compose down
rm -rf /opt/smart_nexus/data/mysql/*
bash /opt/smart_nexus/backend/deploy/cmd/deploy.sh
```

> **预防**：`MYSQL_PASSWORD` 不要包含 `$` 等 shell 特殊字符。

### consultant 报 `Error connecting to 127.0.0.1:6379`（Redis）

`consultant/.env` 缺少 `REDIS_HOST=redis`，容器间必须用服务名通信：

```bash
echo "REDIS_HOST=redis" >> /opt/smart_nexus/backend/consultant/.env
docker compose restart consultant
```

### 百度地图 MCP 连接超时

境外服务器 IP 会被百度 MCP 服务拒绝，属正常现象。服务会降级为无地图工具模式继续运行，知识库问答不受影响。如需导航功能，需迁移至国内（香港或大陆）服务器。

### Nginx 重启后证书报错 `No such file`

nginx 容器内看不到证书，原因是 `docker-compose.yml` 中 SSL 目录挂载未取消注释。参考第六章 6.4 节，取消注释后必须用 `--force-recreate` 重建（不能用 `restart`）：

```bash
cd /opt/smart_nexus/backend/deploy/docker
docker compose up -d --force-recreate nginx
```

### `docker compose` 报 `no configuration file provided`

需在 `docker-compose.yml` 所在目录执行，或通过 `-f` 指定路径：

```bash
docker compose -f /opt/smart_nexus/backend/deploy/docker/docker-compose.yml logs -f consultant
```

### `npm run dev` 前端报 `ECONNREFUSED` 或接口返回 500

**原因**：`front/.env` 中的代理目标地址配置错误或域名解析到了旧 IP。按以下步骤逐一排查：

**步骤 1：确认 `.env` 已配置正确的后端地址**

`front/.env` 中两个代理目标必须指向实际可访问的后端（HTTP 或 HTTPS）：

```ini
VITE_API_TARGET=https://你的域名.com          # knowledge 服务
VITE_CONSULTANT_TARGET=https://你的域名.com   # consultant 服务
```

> 注意：这里填完整域名（不含路径），`VITE_API_BASE_PATH` / `VITE_CONSULTANT_BASE_PATH` 单独配置路径前缀。

**步骤 2：验证 443 端口是否可达**

在本地 Windows PowerShell 执行：

```powershell
Test-NetConnection -ComputerName 你的域名.com -Port 443
```

若 `TcpTestSucceeded: True` 则端口通；若 `False` 则检查云服务商安全组是否已开放 443 入站规则（参考第一章 1.3 节）。

**步骤 3：验证域名解析是否正确**

```cmd
nslookup 你的域名.com
```

若输出的 IP 不是服务器当前 IP，说明本机 DNS 缓存了旧记录，执行：

```cmd
ipconfig /flushdns
```

再次 `nslookup` 确认 IP 已更新。若仍解析到旧 IP，重启路由器（路由器有独立 DNS 缓存），重启后等待约 1 分钟再测试。

**步骤 4：后端无日志打印 → 请求未到达服务器**

若 Vite 控制台报 `ECONNREFUSED`，但服务器 `docker compose logs -f consultant` 毫无打印，说明请求在本机代理阶段就失败了（域名解析失败或端口不通），不是后端问题，继续排查步骤 2/3。

### 域名解析到旧服务器 IP（DNS 缓存问题）

更换服务器并修改 DNS A 记录后，本机可能仍缓存旧 IP，导致请求打到旧服务器（或不存在的地址）。

**排查流程：**

```cmd
# 1. 查看当前解析结果
nslookup 你的域名.com

# 2. 刷新本机 DNS 缓存（需管理员权限的命令提示符）
ipconfig /flushdns

# 3. 再次确认解析结果
nslookup 你的域名.com
```

若刷新后仍是旧 IP，**重启路由器**（路由器有独立缓存），待重启完成（约 1 分钟）后重试。DNS TTL 一般为 5～10 分钟，正常情况重启路由器后即可解析到新 IP。

---

## 附：部署相关文件一览

```
smart_nexus/
  backend/
    deploy/
      cmd/deploy.sh              # 一键部署脚本（从项目根目录执行）
      docker/docker-compose.yml  # 五服务编排
      nginx/nginx.conf           # 反向代理（含 SSE 优化）
      nginx/ssl/                 # SSL 证书（启用 HTTPS 时放入）
      db/smart_nexus.sql         # 数据库初始化脚本（首次启动自动执行）
    knowledge/
      Dockerfile
      .env.example               # 配置模板
      .env                       # 服务器上手动创建，不进 git
    consultant/
      Dockerfile
      .env.example               # 配置模板
      .env                       # 服务器上手动创建，不进 git
  data/                          # 持久化数据（deploy.sh 自动创建，不进 git）
    knowledge/chroma_kb/         # ChromaDB 向量库
    knowledge/crawl/             # 爬虫输出
    consultant/log/              # 运行日志
    consultant/history/          # 对话历史
    mysql/                       # MySQL 数据
    redis/                       # Redis 数据
  front/
    config.json                  # 服务器地址配置，随安装包分发
    electron-dist/               # 打包输出目录（.exe 安装程序）
```
