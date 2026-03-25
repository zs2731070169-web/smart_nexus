# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

两个独立的 FastAPI 后端服务，通过 Docker Compose + Nginx 部署：

| 服务 | 端口 | 职责 |
|------|------|------|
| `consultant/` | 8001 | 多 Agent 智能顾问（对话、鉴权、导航） |
| `knowledge/` | 8000 | 知识库管理（检索、向量化、爬虫） |

## 常用命令

```bash
# 本地启动（工作目录须为项目根）
cd consultant && python -m api.main
cd knowledge  && python -m api.main

# 知识库构建（服务启动后执行，工作目录为项目根）
python -m knowledge.cli.crawl_cli       # 爬取 Lenovo iKnow 文档
python -m knowledge.cli.ingestion_cli   # 向量化写入 ChromaDB

# 测试脚本（工作目录须为 consultant/）
cd consultant
python test/agent_router_test.py   # Agent 路由完整用例（推荐首选）
python test/master_agent_test.py
python test/consult_agent_test.py
python test/navigation_agent_test.py
python test/mcp_test.py
python test/database_test.py

# Docker 部署（工作目录为项目根）
bash deploy/cmd/deploy.sh
```

---

## consultant 模块架构

### API 层（`api/`）

`api/main.py`：FastAPI 根路径 `/smart/nexus`，含 CORS 中间件、`AuthTokenMiddleware` 鉴权，以及 **MCP lifespan**（应用启动时连接 Tavily + 百度地图 MCP，关闭时断开，同时启动 60 秒心跳探活任务）。使用 `anyio.run()` 而非 `asyncio.run()` 保证 cancel scope 统一。

`api/router.py` 注册 6 个端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/code` | 生成验证码（存 Redis 60 秒） |
| POST | `/login` | 验证码登录，返回 JWT |
| DELETE | `/logout` | 登出，更新数据库 `is_login` |
| POST | `/chat` | **核心**：SSE 流式对话 |
| POST | `/query_chat_history` | 列出用户历史会话 |
| DELETE | `/delete_chat_history` | 删除指定会话 |

`/chat` 接收 `query` + `session_id`，IP 从 `X-Forwarded-For → X-Real-IP → client.host` 依次获取，传给 Agent 做定位兜底。

### 三层 Agent 架构

```
coordination_agent（master_agent.py）
    ↓ @function_tool（AGENT_ROUTER）
route_consult_agent / route_navigation_agent（agent_router.py）
    ↓ Runner.run() 同步执行
consult_agent / navigation_agent（node_agents.py）
```

- **第一层**：`coordination_agent` 使用 `main_model`（qwen3.5-plus），`max_turns=5`，流式执行（`Runner.run_streamed()`）
- **第二层**：两个 `@function_tool` 内部调用 `Runner.run()`（非流式），返回 `final_output` 字符串给上层
- **第三层**：
  - `consult_agent`：工具 `[retrieval_knowledge]` + MCP `[web_search_mcp]`
  - `navigation_agent`：工具 `[search_coordinate_source, navigation_sites]` + MCP `[baidu_map_mcp]`
  - 均使用 `sub_model`（qwen3.5-flash），`temperature=0`

### 服务层（`service/`）

**`agent_service.py`**：`stream_messages()` 加载历史消息 → 流式执行 `coordination_agent` → 处理事件 → 保存历史。最多重试 3 次（递归调用），第 3 次失败发送 `EXCEPTION` 结束帧。

**`memory_service.py`**：历史记录保存为 `history/{user_id}/{session_id}.json`，每次加载时截断保留最近 3 轮（6 条非系统消息）。默认系统消息："你是一个智能售后咨询助手"。

**`login_service.py`**：验证码存 `phone_code:{phone}`（Redis），登录锁存 `login_lock:{phone}`（5 秒防重复）。JWT 携带 `user_id` + `iat`；鉴权时比对 `iat` 与数据库 `login_time`，`iat < login_time` 则 token 无效（防旧 token 复用）。

### 本地工具（`infra/tools/local/`）

**`retrieval_knowledge`**：POST `settings.KNOWLEDGE_BASE_URL`，超时 120 秒，返回 JSON 字符串。

**`search_coordinate_source`**：三级降级——① `map_geocode`（地名解析）→ ② `map_ip_location`（IP 定位，境外 IP 自动获取公网 IP via pystun3）→ ③ 北京坐标兜底（116.413383, 39.910924）。直接调用 `baidu_map_mcp.call_tool()`（不经过 Agent 工具调用流程）。

**`navigation_sites`**：对 `repair_shops` 表执行 Haversine 公式 SQL 查询，`LIMIT 3`。

### MCP 层（`infra/tools/mcp/mcp_client.py`）

- `web_search_mcp`、`baidu_map_mcp` 均为 `MCPServerStreamableHttp`，`httpx_client_factory` 设置 `trust_env=False`（不走系统代理）
- `connect()` / `disconnect()` 供 lifespan 调用
- `heartbeat(interval=60)`：每次探活清除 `server._tools` 缓存后调用 `list_tools()`，强制发起网络请求；失败则 `cleanup() → connect()` 重连

### 数据访问层（`infra/db/`、`repo/`）

- **MySQL**：`PooledDB`（DBUtils），`maxconnections=5`，`asyncio.to_thread()` 包装同步操作；`get_cursor()`（读）/ `write_cursor()`（写，自动 commit/rollback）
- **Redis**：`aioredis.ConnectionPool`，`decode_responses=True`；`get_session()` 上下文管理器

### SSE 响应格式（`schema/response.py`）

SSE 帧格式：`data: {StreamMessages.model_dump_json()}\n\n`

```
StreamMessages
  ├── id: str
  ├── status: PROCESSING | FINISHED
  ├── data: DeltaMessage(render_type, data) | FinishMessage
  └── metadata: {create_time, finished_reason: NORMAL|MAX_TOKEN|EXCEPTION, error_message}
```

`render_type`：`THINKING`（推理过程）/ `PROCESSING`（工具调用）/ `ANSWER`（最终回答）

事件映射（`_handle_streaming_event`）：
- `response.output_text.delta` → `ANSWER`
- `response.reasoning_text.delta` → `THINKING`
- `run_item_stream_event[tool_called]` → `PROCESSING`（工具名通过 `TOOL_NAME_MAPPING` 转为中文）

### 配置（`config/settings.py`、`.env`）

必填：`AL_BAILIAN_API_KEY`、`MYSQL_*`、`REDIS_HOST`、`TAVILY_API_KEY`、`BAIDUMAP_AK`、`SECRET_KEY`、`KNOWLEDGE_BASE_URL`

Docker 容器间通信：`MYSQL_HOST=mysql`、`REDIS_HOST=redis`、`KNOWLEDGE_BASE_URL=http://knowledge:8000/...`（使用服务名，不用 IP）

---

## knowledge 模块架构

### API 层（`api/router.py`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/injection/upload` | 上传 .md/.txt 文件，立即向量化 |
| POST | `/retrieval/query` | 检索 + LLM 生成回复 |

### 检索流程（`service/retrieval/retrieval_service.py`）

两路并行检索 → 合并去重 → 重排 → 返回 top_k：

1. **向量检索**：`Chroma.similarity_search()`，L2 范数，top_5
2. **标题关键词检索**：
   - 粗排（top_50）：Jaccard 相似度（jieba 分词 70% + 字符集 30%）
   - 精排（top_5）：标题向量余弦相似度（70%）+ 关键词分 30%
   - 长文档（> CHUNK_SIZE=3000）：取最相似的 3 个分片
3. **去重**：MD5(标题 + 内容前 100 字)
4. **重排**：余弦相似度，动态阈值 0.5

**`query_service.py`**：使用 `gpt-4o-mini` 基于检索结果生成回复；Prompt 要求严格忠实资料、品牌中立、图片以纯文本 URL 展示、结尾注明参考文档。

### 向量化流程（`service/ingestion/`、`repo/vector_repo.py`）

- 分片策略：`RecursiveCharacterTextSplitter`，separators 优先级：`\n## > \n** > \n\n > \n > 空格 > 字符`，chunk_size=3000，overlap=300
- 分片时 `page_content` 格式：`"主题：{filename}\n\n内容：{chunk_text}"`
- 向量模型：`text-embedding-3-large`（OpenAI 兼容接口）
- 向量库：Chroma，collection `smart_nexus`，持久化到 `knowledge/chroma_kb/`

### CLI 工具

**`crawl_cli.py`**：爬取 Lenovo iKnow（`settings.KNOWLEDGE_BASE_URL`），连续失败 5 次暂停 60 秒，每条间隔 0.2 秒，输出到 `knowledge/data/crawl/{id:04d}_{title}.md`。爬取范围 `range(0, 2000)` 硬编码在脚本中，增量更新需手动修改。

**`ingestion_cli.py`**：批量处理（batch_size=20），`FileUtils.remove_duplicate_files()` 自动去重，重复执行会追加而非覆盖（Chroma 不去重，清空需手动删除 `chroma_kb/`）。

### 配置

必填：`API_KEY`（OpenAI 兼容）

路径均为相对路径，工作目录须为项目根，例如 `VECTOR_STORE_PATH=knowledge/chroma_kb`。
