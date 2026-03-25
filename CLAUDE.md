# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## consultant 模块架构

`consultant/` 是多 Agent 智能顾问后端，基于 OpenAI Agents SDK 构建三层 Agent 调度架构，对外（目前）尚无 FastAPI 入口（`api/` 目录只有 `__init__.py`）。

### 三层 Agent 架构

```
coordination_agent（master_agent.py）
    ↓ 工具调用（AGENT_ROUTER）
route_consult_agent / route_navigation_agent（agent_router.py）
    ↓ Runner.run() 异步运行
consult_agent / navigation_agent（node_agents.py）
```

- **第一层 - 主控**（`master_agent.py`）：`coordination_agent` 接收用户意图，通过 `AGENT_ROUTER` 中的 `@function_tool` 路由到对应专家 Agent
- **第二层 - 路由**（`agent_router.py`）：`route_consult_agent` / `route_navigation_agent` 是 `@function_tool` 包装函数，内部调用 `Runner.run()` 异步启动叶节点 Agent 并返回 `final_output`
- **第三层 - 叶节点**（`node_agents.py`）：
  - `consult_agent`：售后技术咨询，持有 `retrieval_knowledge`（本地工具）+ `web_search_mcp`（Tavily 网络搜索，知识库无结果时降级）
  - `navigation_agent`：服务站导航，持有 `search_coordinate_source` + `navigation_sites`（本地工具）+ `baidu_map_mcp`（百度地图）

### 工具体系

**本地工具**（`infra/tools/local/`）：
- `retrieval_knowledge`：`@function_tool`，POST 调用 knowledge 服务的 `/retrieval/query` 接口
- `search_coordinate_source`：`@function_tool`，优先用地名 geocode，失败则用公网 IP 定位，最终兜底北京坐标
- `navigation_sites`：`@function_tool`，对 MySQL `repair_shops` 表执行 Haversine 公式查询最近维修站（`LIMIT 3`）

**MCP 工具**（`infra/tools/mcp/`，`MCPServerStreamableHttp`）：
- `web_search_mcp`：Tavily 搜索，供 `consult_agent` 降级使用
- `baidu_map_mcp`：百度地图，提供 `map_geocode` / `map_ip_location` / `map_url` 工具

**MCP 生命周期**：MCP 连接需在 `AsyncExitStack` 中管理，测试脚本中有参考用法（`test/agent_router_test.py`）。叶节点 Agent 定义时直接引用 MCP 实例，连接在 Agent 运行前必须已建立。

### 流式响应协议（SSE）

`schema/response.py` 定义 SSE 消息格式：

- `DeltaMessage`：分片消息，含 `render_type`（`THINKING`/`PROCESSING`/`ANSWER`）和 `data` 文本
- `FinishMessage`：结束消息
- `StreamMessages`：外层包装，含 `id`、`status`（`PROCESSING`/`FINISHED`）、`metadata`（`finished_reason`：`NORMAL`/`MAX_TOKEN`/`EXCEPTION`）

工具辅助函数：`build_processing_stream_messages(data, render_type)` / `build_finished_stream_messages(message_id)`

`constants/enums.py` 中的 `TOOL_NAME_MAPPING` 将工具函数名映射到用户可读的中文名称（供前端渲染工具调用过程）。

### 测试脚本

所有测试均为独立脚本（直接 `python` 运行，工作目录须为 `consultant/`）：

```bash
# 测试 Agent 路由（含 consult_agent 和 navigation_agent 完整用例）
cd consultant && python test/agent_router_test.py

# 其他测试脚本
python test/master_agent_test.py
python test/consult_agent_test.py
python test/navigation_agent_test.py
python test/mcp_test.py
python test/database_test.py
```

### 配置项（`.env`）

必填（二选一）：`SF_API_KEY`（Silicon Flow）或 `AL_BAILIAN_API_KEY`（阿里百炼）

其他必填：`MYSQL_HOST`/`MYSQL_PORT`/`MYSQL_USER`/`MYSQL_PASSWORD`/`MYSQL_DATABASE`、`TAVILY_API_KEY`、`TAVILY_BASE_URL`、`BAIDUMAP_AK`、`BAIDUMAP_BASE_URL`、`KNOWLEDGE_BASE_URL`（knowledge 服务地址）
