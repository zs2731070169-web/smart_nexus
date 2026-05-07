# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Smart Nexus 是一个 AI 原生的智能售后顾问系统，由两个独立的 FastAPI 微服务组成：

- **consultant**（端口 8001）：多 Agent 编排 + MCP 工具的对话服务，SSE 流式响应。`root_path=/smart/nexus`，路由前缀再加 `/consultant`。
- **knowledge**（端口 8000）：RAG 知识库服务（爬取 → 切片 → 向量化 → 双路召回）。`root_path=/smart/nexus/knowledge`。

两个服务**不共享 Python 包**，各自有独立的 `requirements.txt` / `setup.py` / `Dockerfile`，通过 HTTP 互通（consultant 调用 knowledge 的 `/retrieval/query`）。

更详细的部署、架构、难点说明见 `DEPLOY.md` 与 `项目介绍-面试版.md`。

## 常用命令

### 本地开发（不走 Docker）

```powershell
# consultant 服务
cd F:\projects\smart_nexus\consultant
pip install -r requirements.txt
python -m api.main          # 监听 0.0.0.0:8001（端口由 .env 的 APP_PORT 决定）

# knowledge 服务
cd F:\projects\smart_nexus\knowledge
pip install -r requirements.txt
python -m api.main          # 监听 0.0.0.0:8000
```

两个服务都依赖 `.env`（不进 git，模板见对应目录的 `.env.example`）。`consultant/config/settings.py` 在启动期 fail-fast，必填项缺失会一次性抛出全部错误，不要补 default。

### 测试

```powershell
# consultant：每个测试文件独立可运行（内部用 unittest.main）
cd F:\projects\smart_nexus\consultant
python test/unit_test.py             # 纯逻辑单测，无需 DB/Redis
python test/agent_router_test.py     # 单文件单测
python test/integration_test.py      # 集成测试（需服务已启动）
python test/sse_api_test.py          # SSE 接口测试

# knowledge：使用标准 unittest discover
cd F:\projects\smart_nexus\knowledge
python -m unittest discover -s test -v
python -m unittest test.retrieval_service_test
```

注：`unit_test.py` 头部会 `os.environ.setdefault` 注入 `SECRET_KEY` 等假值绕过 settings 校验；新写测试时同样要保证 `SECRET_KEY ≥ 32 字节`，否则 PyJWT 会拒绝。

### 知识库构建（在 knowledge 容器/本地执行）

```bash
# 1) 爬取范围在 knowledge/cli/crawl_cli.py 中硬编码的 range(...) 里改
python -m cli.crawl_cli       # 输出到 data/knowledge/crawl/
python -m cli.ingestion_cli   # 摄入到 ChromaDB（基于文件 hash 自动去重，重复执行只追加）
```

清空向量库需手动 `rm -rf data/knowledge/chroma_kb/*` 后重新摄入。

### Docker 部署

```bash
# 一键部署（从项目根执行；脚本会读 consultant/.env 的 MYSQL_PASSWORD）
bash deploy/cmd/deploy.sh

# 日常运维（在 deploy/docker 目录下执行 docker compose）
cd deploy/docker
docker compose ps
docker compose logs -f consultant
docker compose up -d --build consultant            # 改了代码/requirements 后
docker compose up -d --force-recreate consultant   # 仅改了 .env 后
docker compose exec nginx nginx -s reload          # 改了 nginx.conf 后
```

## 架构关键点

### 三层 Agent + 双注册器（consultant 核心）

```
coordination_agent (L1, ReAct, max_turns=15)
   tools = agent_router_registry.routes()
        │
        ├─ route_consult_agent      ──→ consult_agent      (L3)
        └─ route_navigation_agent   ──→ navigation_agent   (L3)
                                          tools/mcp = tool_registry.{function_tools(), mcp_servers()}
```

- **`infra/tools/base.py`** 定义 `BaseTool`（`execute(args:BaseModel) -> ToolResult`）+ `ToolRegistry`（同时管 local 工具和 MCP server）。新增工具：写一个继承 `BaseTool` 的类，在 `infra/tools/__init__.py` 加一行 `tool_registry.register(...)`，**不要**改 agent 定义。
- **`agent/agent_router.py`** 定义 `AgentRouterRegistry`：`register(agent, description)` 用闭包把 `Runner.run(agent)` 包装成 `route_{agent.name}` 形式的 `FunctionTool`，子 agent 输出统一封装为 `{status, summary, tool_calls, error_message?}` JSON envelope（见 `constants/enums.RouteStatus`）。新增子 agent：在 `agent/node_agents.py` 定义实例，在 `agent/__init__.py` 加一行 `agent_router_registry.register(...)`。
- **主控**通过 envelope 的 `status` 决定是否 replan，通过 `tool_calls` 观测子 agent 实际用了哪些工具。

不要在 agent 定义中硬编码工具列表，也不要为每个子 agent 单独手写 `@function_tool route_xxx` 模板——这是被刻意重构掉的反模式。

### MCP 长连接保活

`infra/tools/mcp/mcp_client.py` 在 FastAPI lifespan（`api/main.py`）启动 60 秒心跳协程，探活前会 `server._tools = None` 清缓存（`cache_tools_list=True` 的 SDK 缓存陷阱），失败立即 `cleanup()→connect()`。`httpx_client_factory(trust_env=False)` 隔离宿主代理。**主入口用 `anyio.run()` 而非 `asyncio.run()`**，以便 cancel scope 在统一上下文里收敛。

### SSE 流式协议

- 协议模型：`schema/response.StreamMessages`，`render_type ∈ {THINKING, PROCESSING, ANSWER, EXCEPTION}`。
- `<think>...</think>` 标签流式拆分：`utils/tag_extract_utils.py` 是字符级状态机，跨 chunk 拼接半个标签；切换 agent / 工具调用时必须 `flush` 残留 buf。
- `service/agent_service.stream_messages()` 自带指数退避重试（`MAX_TRY_COUNT=20`，`min(0.5*2^n, 10)` 秒），`ValueError` 短路不重试，最终失败发 `EXCEPTION` 终止帧。

### 鉴权（软吊销 JWT）

JWT payload 写 `iat`，DB `user.login_time` 比对：新登录刷新 `login_time` → 所有旧 token 立即失效。`AuthTokenMiddleware` 走白名单（`config/settings.py` 的 `WHITE_LIST`，目前是 `/code` 和 `/login`）。Redis `login_lock:{phone}` 5 秒短锁防爆破。

### 上下文截断

历史持久化为 `data/consultant/history/{user_id}/{session_id}.json`，但加载只保留最近 3 轮（6 条非系统消息），系统消息单独分组不参与截断。用户 IP 通过附加 user 消息（`[非用户问题，用户当前ip：xxx]`）透传给 agent，**不写入历史**。

### 知识库双路召回

`knowledge/service/retrieval/`：
- 路 A：Chroma 向量检索（top_5）
- 路 B：标题关键词召回 → Jaccard 粗排（jieba 70% + 字符集 30%）→ 标题向量+关键词分精排
- MD5（`title + content[:100]`）去重合并 → 余弦 0.5 阈值丢弃

修改召回逻辑务必保持双路独立，不要合并成单路向量检索。

### 三级降级定位（navigation）

`map_geocode → map_ip_location → pystun3 公网 IP 重试 → 北京坐标兜底 (116.4133, 39.9109)`。`api/router._get_client_ip` 顺序：`X-Forwarded-For[0] → X-Real-IP → request.client.host`。BD09 ↔ WGS84 转换在 `utils/map_utils.py`。

## 项目约定

- **始终用简体中文**回复、写文档、写代码注释（用户全局规则）。
- 默认使用 **MiniMax-M2.7-highspeed**（OpenAI 兼容接口，支持 `enable_thinking` 原生思维链）作为主/子 Agent 模型；知识库生成用 `gpt-4o-mini`，向量化用 `text-embedding-3-large`。
- consultant 容器间通信**必须**用服务名（`MYSQL_HOST=mysql`、`REDIS_HOST=redis`、`KNOWLEDGE_BASE_URL=http://knowledge:8000/...`），不要写 localhost / 127.0.0.1。
- `.env` 中的 `MYSQL_PASSWORD` **不要**包含 `$` 等 shell 特殊字符，会被 deploy.sh 误展开。
- 部署相关 nginx.conf 是 HTTPS-only（80 强制跳 443），首次部署前必须先签 SSL 证书放到 `deploy/nginx/ssl/`，否则 nginx 容器起不来。
