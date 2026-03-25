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

## 三、配置域名与 HTTPS

> **必须步骤**：`nginx.conf` 已配置为 HTTPS 专用模式（HTTP 80 强制跳转 HTTPS，无 HTTP 直连选项）。**不完成本章，nginx 容器将无法启动。** 请在启动服务之前完成本章所有步骤。

前置条件：已购买域名，并在域名服务商控制台将 A 记录解析到服务器公网 IP，等待 DNS 生效（通常 5～10 分钟）。

### 3.1 修改 nginx.conf 中的域名

`nginx.conf` 中已写好 HTTPS 配置，只需将域名替换为你的实际域名：

```bash
nano /opt/smart_nexus/deploy/nginx/nginx.conf
```

将文件中所有 `www.apidev-app.com` 替换为你的域名（共 2 处：HTTP 跳转块和 HTTPS server 块各一处）：

```nginx
# HTTP 跳转块
server_name 你的域名.com;

# HTTPS server 块
server_name 你的域名.com;
```

### 3.2 申请 SSL 证书

> 前提：域名 DNS 已解析到服务器 IP，且 80 端口未被占用（首次部署时服务尚未启动，80 端口空闲，直接申请即可）。

```bash
sudo apt install -y certbot

# 申请证书（首次部署，服务未启动，直接运行）
sudo certbot certonly --standalone -d 你的域名.com
```

> **如果服务已经在运行**（更换证书时），需先释放 80 端口：
> ```bash
> cd /opt/smart_nexus/deploy/docker
> docker compose stop nginx
> sudo certbot certonly --standalone -d 你的域名.com
> docker compose start nginx
> ```

### 3.3 挂载证书

```bash
mkdir -p /opt/smart_nexus/deploy/nginx/ssl
sudo cp /etc/letsencrypt/live/你的域名.com/fullchain.pem \
        /opt/smart_nexus/deploy/nginx/ssl/
sudo cp /etc/letsencrypt/live/你的域名.com/privkey.pem \
        /opt/smart_nexus/deploy/nginx/ssl/
```

### 3.4 设置证书自动续签

Let's Encrypt 证书有效期 90 天，设置 cron 每月自动续签：

```bash
(crontab -l 2>/dev/null; echo "0 3 1 * * certbot renew --quiet && \
  cp /etc/letsencrypt/live/你的域名.com/fullchain.pem /opt/smart_nexus/deploy/nginx/ssl/ && \
  cp /etc/letsencrypt/live/你的域名.com/privkey.pem /opt/smart_nexus/deploy/nginx/ssl/ && \
  docker compose -f /opt/smart_nexus/deploy/docker/docker-compose.yml restart nginx") | crontab -
```

---

## 四、配置环境变量

> 这是部署最关键的步骤，两个 `.env` 文件均不进 git，需在服务器上手动创建。

### 4.1 knowledge 后端

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

### 4.2 consultant 后端

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

## 五、启动后端服务

`deploy.sh` 会自动完成：检查依赖 → 读取 MySQL 密码 → 创建数据目录 → 构建并启动所有容器。

```bash
cd /opt/smart_nexus
bash deploy/cmd/deploy.sh
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
[INFO]  📡 访问地址：https://你的域名.com
```

---

## 六、验证后端服务

### 6.1 确认容器全部正常运行

```bash
cd /opt/smart_nexus/deploy/docker
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

### 6.2 验证接口联通性

```bash
# 测试 knowledge 服务
curl https://你的域名.com/smart/nexus/knowledge/retrieval/query \
  -X POST -H "Content-Type: application/json" \
  -d '{"question":"测试","top_k":1}'

# 测试 consultant 获取验证码接口
curl -X POST https://你的域名.com/smart/nexus/consultant/code \
  -H "Content-Type: application/json" \
  -d '{"user_phone":"13800000000"}'
# 期望返回：{"status":"200",...}
```

### 6.3 出错时查看日志

```bash
cd /opt/smart_nexus/deploy/docker
docker compose logs -f consultant
docker compose logs -f knowledge
docker compose logs -f mysql
```

---

## 七、构建知识库

> 在**服务器**上执行，需要后端服务已正常运行。

知识库构建分两步：**爬取文档** → **向量化摄入**。爬取结果存放在持久化目录 `data/knowledge/crawl/`，摄入后写入 ChromaDB（`data/knowledge/chroma_kb/`），两步均通过 `docker compose exec` 在 knowledge 容器内运行。

### 7.1 设置爬取范围

爬取编号范围在代码中硬编码，**每次爬取前需先修改**：

```bash
nano /opt/smart_nexus/knowledge/cli/crawl_cli.py
```

找到以下行，将 `range(0, 2000)` 改为实际需要爬取的编号区间：

```python
for i in range(0, 2000):   # ← 修改起止编号（首次全量建库建议 0~2000）
```

> 说明：编号对应 Lenovo iKnow 知识条目序号，不连续的编号会自动跳过（返回空则跳过）。

### 7.2 执行爬取

```bash
cd /opt/smart_nexus/deploy/docker
docker compose exec knowledge python -m cli.crawl_cli
```

爬取过程中会实时打印日志，每爬一条休眠 0.2 秒；连续失败 5 次自动暂停 60 秒等待服务端恢复。全量 2000 条约需 **15～30 分钟**。

爬取完成后，文件保存在服务器的 `/opt/smart_nexus/data/knowledge/crawl/` 目录下，命名格式为 `{编号:04d}_{标题}.md`。

### 7.3 构建向量知识库（摄入）

爬取完成后执行摄入，将 Markdown 文件向量化写入 ChromaDB：

```bash
cd /opt/smart_nexus/deploy/docker
docker compose exec knowledge python -m cli.ingestion_cli
```

摄入过程显示进度条，格式为 `知识库上传进度: X%|... 成功块数: N 失败批次: M`。

> **注意**：
> - 重复执行摄入不会清空旧数据，会追加写入。如需重建，先手动清空 ChromaDB 目录（见下方命令）。
> - 摄入的是 `data/knowledge/crawl/` 下的所有 `.md` 文件，包括历史爬取结果。

**重建知识库（清空后重新摄入）：**

```bash
# ⚠️ 以下操作会清除全部向量数据，需重新摄入
rm -rf /opt/smart_nexus/data/knowledge/chroma_kb/*
cd /opt/smart_nexus/deploy/docker
docker compose exec knowledge python -m cli.ingestion_cli
```

### 7.4 增量更新

如需追加新的知识条目（如已爬取 0\~999，现在追加 1000\~1999）：

1. 修改 `crawl_cli.py` 中 `range` 改为 `range(1000, 2000)`
2. 重新执行爬取（新文件保存到 `crawl/` 目录，不覆盖旧文件）
3. 重新执行摄入（已向量化的内容会基于文件哈希自动去重，只追加新内容）

---

## 八、日常运维与更新发布

### 8.1 常用运维命令

```bash
# 工作目录（以下命令均在此目录执行）
cd /opt/smart_nexus/deploy/docker

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

# 更新 nginx.conf 后热重载（无需重建容器）
docker compose exec nginx nginx -s reload

# 验证 nginx 配置语法
docker compose exec nginx nginx -t

# 停止所有服务
docker compose down

# 停止并清除数据卷（⚠️ 数据库数据会丢失）
docker compose down -v
```

### 8.2 后端代码更新发布

**步骤 1：拉取最新代码**

```bash
cd /opt/smart_nexus
git pull
```

**步骤 2：重新构建并启动容器**

```bash
# 方式 A：全量重新部署（推荐，适用于任何改动）
bash deploy/cmd/deploy.sh

# 方式 B：仅重建指定服务（改动范围明确时使用，速度更快）
cd deploy/docker
docker compose up -d --build knowledge    # 仅更新 knowledge
docker compose up -d --build consultant   # 仅更新 consultant
```

> **选哪种方式**：
> - 修改了 Python 代码或 `requirements.txt` → 方式 A 或方式 B，`--build` 会重建镜像并自动重建容器，无需额外操作
> - 只修改了 `.env` 配置（代码无变化）→ 方式 B 加 `--force-recreate`（镜像未变，需强制重建容器使新环境变量生效）
> - 修改了 `docker-compose.yml` 的 volumes / ports → 用方式 B 加 `--force-recreate`（方式 A 的 `deploy.sh` 不带该参数，无法生效）

**修改了环境变量（`.env`）后重启：**

```bash
cd /opt/smart_nexus/deploy/docker
docker compose up -d --force-recreate consultant
```

---

## 九、常见问题排错

### consultant 启动报 `Connection refused`（MySQL）

MySQL 首次启动需执行初始化 SQL，耗时 1～2 分钟。`deploy.sh` 已配置健康检查，consultant 会自动等待，无需手动干预。若等待超过 3 分钟仍未启动，执行：

```bash
cd /opt/smart_nexus/deploy/docker
docker compose logs mysql   # 查看 MySQL 初始化日志
```

### consultant 报 `Access denied for user 'root'`（MySQL 密码不匹配）

MySQL 数据目录已用旧密码初始化，修改密码后需清空重建：

```bash
cd /opt/smart_nexus/deploy/docker
docker compose down
rm -rf /opt/smart_nexus/data/mysql/*
bash /opt/smart_nexus/deploy/cmd/deploy.sh
```

> **预防**：`MYSQL_PASSWORD` 不要包含 `$` 等 shell 特殊字符。

### consultant 报 `Error connecting to 127.0.0.1:6379`（Redis）

`consultant/.env` 缺少 `REDIS_HOST=redis`，容器间必须用服务名通信：

```bash
echo "REDIS_HOST=redis" >> /opt/smart_nexus/consultant/.env
docker compose restart consultant
```

### 百度地图 MCP 连接超时

境外服务器 IP 会被百度 MCP 服务拒绝，属正常现象。服务会降级为无地图工具模式继续运行，知识库问答不受影响。如需导航功能，需迁移至国内（香港或大陆）服务器。

### Nginx 重启后证书报错 `No such file`

nginx 容器内看不到证书，通常是证书文件未复制到 `nginx/ssl/` 目录。参考第三章 3.3 节重新挂载证书，然后重建 nginx 容器：

```bash
cd /opt/smart_nexus/deploy/docker
docker compose up -d --force-recreate nginx
```

### `docker compose` 报 `no configuration file provided`

需在 `docker-compose.yml` 所在目录执行，或通过 `-f` 指定路径：

```bash
docker compose -f /opt/smart_nexus/deploy/docker/docker-compose.yml logs -f consultant
```

---

## 附：部署相关文件一览

```
smart_nexus/
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
  data/                        # 持久化数据（deploy.sh 自动创建，不进 git）
    knowledge/chroma_kb/       # ChromaDB 向量库
    knowledge/crawl/           # 爬虫输出
    consultant/log/            # 运行日志
    consultant/history/        # 对话历史
    mysql/                     # MySQL 数据
    redis/                     # Redis 数据
```
