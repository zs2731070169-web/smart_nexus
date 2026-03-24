#!/bin/bash
# ============================================================
# Smart Nexus 一键部署脚本
# 执行方式：bash backend/deploy/cmd/deploy.sh（从项目根目录执行）
# ============================================================

set -e # 遇到任何非零退出码的命令立即终止脚本,只要失败就不继续执行，避免部署进入不可控状态

# ============================================================
# 颜色 & 工具函数
# ============================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }
step()  { echo -e "\n${BLUE}==============================${NC}\n${BLUE} $1 ${NC}\n${BLUE}==============================${NC}"; }

# ============================================================
# 路径定义（以脚本自身位置为基准，不依赖执行目录）
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$SCRIPT_DIR/.."           # backend/deploy/
DOCKER_DIR="$DEPLOY_DIR/docker"       # backend/deploy/docker/
KNOWLEDGE_ENV="$DEPLOY_DIR/../knowledge/.env"    # backend/knowledge/.env
CONSULTANT_ENV="$DEPLOY_DIR/../consultant/.env"  # backend/consultant/.env
NGINX_CONF="$DEPLOY_DIR/nginx/nginx.conf"           # backend/deploy/nginx/nginx.conf
DATA_DIR="$DEPLOY_DIR/../../data"     # backend/data/

# ============================================================
# ① 检查环境依赖
# ============================================================
step "① 检查环境依赖"

if ! command -v docker &>/dev/null; then
    error "未检测到 Docker，请先安装：https://docs.docker.com/get-docker/"
fi
info "Docker：$(docker --version)"

if ! docker compose version &>/dev/null; then
    error "未检测到 Docker Compose v2，请升级 Docker 至最新版"
fi
info "Docker Compose：$(docker compose version)"

if ! docker info &>/dev/null; then
    error "Docker 未启动，请先启动 Docker 服务"
fi
info "Docker 服务运行正常 ✓"

# ============================================================
# ② 检查配置文件
# ============================================================
step "② 检查配置文件"

[ ! -f "$KNOWLEDGE_ENV" ]  && error "缺少 knowledge 配置：$KNOWLEDGE_ENV\n       请参考 knowledge/.env.example 创建"
info "knowledge/.env ✓"

[ ! -f "$CONSULTANT_ENV" ] && error "缺少 consultant 配置：$CONSULTANT_ENV\n       请参考 consultant/.env.example 创建"
info "consultant/.env ✓"

[ ! -f "$NGINX_CONF" ]     && error "缺少 nginx 配置：$NGINX_CONF"
info "nginx.conf ✓"

# ============================================================
# ③ 读取 MySQL 密码
# ============================================================
step "③ 读取 MySQL 密码"

# 从 consultant/.env 的 MYSQL_PASSWORD 读取，作为 MySQL root 密码
MYSQL_ROOT_PASSWORD=$(grep -E '^MYSQL_PASSWORD=' "$CONSULTANT_ENV" | cut -d'=' -f2 | tr -d '[:space:]' || true)

if [ -z "$MYSQL_ROOT_PASSWORD" ]; then
    warn "consultant/.env 中未配置 MYSQL_PASSWORD，请手动输入"
    read -rsp "请输入 MySQL root 密码：" MYSQL_ROOT_PASSWORD # 从终端读取用户输入并赋值给变量,-r 禁止对反斜杠进行转义, -s 在输入时不会回显, -p 后面跟提示文本
    echo
fi

[ -z "$MYSQL_ROOT_PASSWORD" ] && error "MySQL 密码不能为空"

export MYSQL_ROOT_PASSWORD # 导出为环境变量，子进程可读

# 同时写入 docker/.env，确保 docker compose 变量替换时能读到（export 有时在子 shell 中失效）
DOCKER_ENV_FILE="$DOCKER_DIR/.env"
if grep -q '^MYSQL_ROOT_PASSWORD=' "$DOCKER_ENV_FILE" 2>/dev/null; then
    sed -i "s|^MYSQL_ROOT_PASSWORD=.*|MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD|" "$DOCKER_ENV_FILE"
else
    echo "MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD" >> "$DOCKER_ENV_FILE"
fi
info "MySQL 密码已加载 ✓"

# ============================================================
# ④ 创建数据持久化目录
# ============================================================
step "④ 创建数据持久化目录"

mkdir -p "$DATA_DIR/knowledge/chroma_kb"
mkdir -p "$DATA_DIR/knowledge/crawl"
mkdir -p "$DATA_DIR/consultant/log"
mkdir -p "$DATA_DIR/consultant/history"
mkdir -p "$DATA_DIR/mysql"
mkdir -p "$DATA_DIR/redis"

info "数据目录：$DATA_DIR ✓"

# ============================================================
# ⑤ 构建并启动所有服务
# ============================================================
step "⑤ 构建并启动服务"

cd "$DOCKER_DIR"
docker compose up -d --build

# ============================================================
# ⑥ 等待服务就绪并展示状态
# ============================================================
step "⑥ 检查服务状态"

info "等待服务启动（15s）..."
sleep 15

docker compose ps

echo ""
info "🚀 Smart Nexus 部署完成！"
info "📡 访问地址：http://$(hostname -I | awk '{print $1}')" # 返回主网卡ip
echo ""
info "常用命令："
info "  查看日志：docker compose -f $DOCKER_DIR/docker-compose.yml logs -f"
info "  停止服务：docker compose -f $DOCKER_DIR/docker-compose.yml down"
info "  重启服务：docker compose -f $DOCKER_DIR/docker-compose.yml restart"