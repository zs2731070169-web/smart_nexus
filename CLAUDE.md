# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Smart Nexus 是一个电脑售后智能知识顾问系统，由两个独立后端服务组成：`knowledge`（RAG 知识库问答）和 `consultant`（多 Agent 智能顾问）。`knowledge` 从 Lenovo iKnow 平台爬取数据，向量化存储到 Chroma；`consultant` 通过 OpenAI Agents SDK 协调多个专职 Agent，调用 `knowledge` 检索接口作为工具之一。前端提供聊天式交互界面和知识库文档上传功能。

> **详细模块说明**：`backend/consultant/` 的架构细节见 `backend/CLAUDE.md`。

## 技术栈

### 后端（`backend/knowledge/`）—— RAG 知识库服务
- **语言**: Python 3
- **Web 框架**: FastAPI + Uvicorn
- **AI/LLM**: LangChain（langchain-core, langchain-openai, langchain-community, langchain-classic）
- **向量数据库**: Chroma（langchain-chroma），collection 名称为 `smart_nexus`
- **中文处理**: jieba 分词（用于关键词匹配）、BeautifulSoup（HTML 清洗）
- **配置管理**: pydantic-settings，环境变量通过 `backend/knowledge/.env` 加载

### 后端（`backend/consultant/`）—— 多 Agent 智能顾问
- **AI 框架**: OpenAI Agents SDK（`openai-agents`）
- **LLM**: Silicon Flow（Qwen3-32B，协调层）+ Alibaba Bailian（qwen-flash/qwen3-max，子 Agent）
- **数据库**: MySQL（DBUtils 连接池，Haversine 查询最近维修站）
- **MCP 工具**: Tavily（网络搜索 fallback）+ 百度地图（geocoding / 导航 URI）
- **配置管理**: pydantic-settings，环境变量通过 `backend/consultant/.env` 加载

### 前端（`front/`）
- **框架**: Vue 3（Options API + `setup()`）+ Vite 6
- **UI 库**: Element Plus（按需加载，通过 unplugin-vue-components + unplugin-auto-import）
- **图标**: @element-plus/icons-vue（显式具名导入，天然 tree-shakeable）
- **HTTP**: Axios（统一封装在 `src/api/request.js`，baseURL 为 `/api`）
- **Markdown 渲染**: marked（自定义 renderer 将图片链接渲染为 `<img>`）

## 常用命令

```bash
# ===== knowledge 后端 =====
# 安装依赖
cd backend/knowledge && pip install -r requirements.txt
# 或以开发模式安装
cd backend/knowledge && pip install -e .

# 启动 API 服务（默认端口 8000，可通过 APP_PORT 环境变量修改）
cd backend/knowledge && python -m api.main

# 运行爬虫（从 iKnow 批量爬取知识库数据）
cd backend/knowledge && python -m cli.crawl_cli

# 批量摄入文档到向量库（将 crawl 目录下的 md 文件向量化）
cd backend/knowledge && python -m cli.ingestion_cli

# 运行手动测试脚本（test/ 目录下均为独立脚本，非 pytest）
cd backend/knowledge && python test/retrieval_service_test.py

# ===== consultant 后端 =====
# 安装依赖（开发模式）
cd backend/consultant && pip install -e .

# 环境变量配置（首次使用）
cd backend/consultant && cp .env.example .env  # 填写后使用
# 必须配置 SF_API_KEY 或 AL_BAILIAN_API_KEY 之一，否则 settings 初始化时抛异常

# ===== 前端 =====
# 安装依赖
cd front && npm install

# 启动开发服务器（默认端口 3000，通过 .env 中 VITE_PORT 配置）
cd front && npm run dev

# 生产构建
cd front && npm run build
```

**注意**: 目前没有配置 linting 工具和正式测试框架。后端 `test/` 目录下的文件是手动测试脚本（直接 `python` 运行），不基于 pytest 或 unittest。前端无测试配置。

## 架构

```
backend/
  knowledge/               # RAG 知识库服务（setup.py + requirements.txt 各自独立）
  api/
    main.py                # FastAPI 应用入口（root_path="/smart/nexus/knowledge"）
    router.py              # 路由定义：POST /injection/upload, POST /retrieval/query
    schema.py              # Pydantic 请求/响应模型
  cli/
    crawl_cli.py           # 爬虫 CLI 入口（爬取范围在代码中硬编码，每次使用前需修改 range）
    ingestion_cli.py       # 批量摄入 CLI 入口（按 batch_size=20 分批处理）
  config/settings.py       # Pydantic BaseSettings 全局配置（单例 settings）
  repo/vector_repo.py      # Chroma 向量数据库操作封装
  service/
    crawler/               # 网页爬虫（从 iKnow 爬取并转 Markdown）
    ingestion/             # 数据摄入（Markdown → 分块 → 向量化）
    retrieval/             # 检索服务（两路检索 + 去重 + 重排序）
  utils/                   # 文件操作工具、HTML 清洗

  consultant/              # 多 Agent 智能顾问（setup.py + requirements.txt 各自独立）
    agent/
      multi_agents.py      # 三个 Agent 定义：Consult Agent、Navigation Agent、Coordinator（未完成）
    infra/
      ai/ai_client.py      # LLM 客户端（Silicon Flow + Alibaba Bailian，OpenAI 兼容接口）
      db/database.py       # MySQL 连接池（DBUtils.PooledDB），async get_cursor() 上下文管理
      tools/local/         # 本地工具：retrieval_knowledge（调 knowledge HTTP API）、map_navigation
      tools/mcp/           # MCP 客户端：Tavily 搜索 + 百度地图
      logging/logger.py    # 控制台 + 文件轮转日志（写入 log/ 目录）
    config/settings.py     # Pydantic BaseSettings 全局配置（单例 settings）
    prompts/               # Agent 系统 Prompt（.md 文件，通过 file_utils.load_prompt() 加载）
    utils/                 # file_utils、ip_utils、map_utils

front/                     # 前端 Vue 3 应用
  src/
    main.js                # 应用入口，仅挂载 App（无全局插件注册）
    App.vue                # 根组件：左侧边栏 + 右侧聊天区布局
    api/
      request.js           # Axios 实例封装（baseURL=/api, 超时 120s）
      knowledge.js         # API 函数：uploadFile, queryKnowledge
    components/
      ChatPanel/           # 聊天面板（消息列表 + Markdown 渲染 + 输入框）
      UploadPanel/         # 文件上传面板（拖拽上传 .md/.txt）
    assets/styles/
      global.css           # 全局样式重置
  .env                     # 环境变量（VITE_PORT, VITE_API_TARGET, VITE_API_BASE_PATH）
  vite.config.js           # Vite 配置（按需加载插件 + loadEnv 读取环境变量 + API 代理）
```

## 前后端交互

前端所有 API 请求以 `/api` 为前缀，Vite 开发服务器通过 proxy 将 `/api` 重写为后端实际路径 `/smart/nexus/knowledge`，转发到后端（默认 `http://127.0.0.1:8000`）。相关配置在 `front/.env` 和 `front/vite.config.js` 中。

后端 API 端点：
- `POST /injection/upload` — 上传文件到知识库（multipart/form-data）
- `POST /retrieval/query` — 知识库检索问答（JSON: `{ question, top_k }`）

响应格式约定：`status === '200'` 表示成功，`content` 为回答内容，`description` 为错误描述。

## 前端 Element Plus 按需加载机制

- **组件**（`el-button`、`el-input` 等）：由 `unplugin-vue-components` 在编译时自动按需引入，模板中直接使用即可
- **JS API**（`ElMessage`、`ElMessageBox` 等）：由 `unplugin-auto-import` 自动引入，代码中直接调用即可，无需 import
- **图标**：需在各组件中显式 `import { IconName } from '@element-plus/icons-vue'` 并注册到 `components`

## 核心数据流

### 爬虫生成的 Markdown 结构

`text_parser_service.py` 将 iKnow API 返回的 JSON 转换为固定结构的 Markdown：

```
# 知识库条目:{knowledge_no}
## 标题 / ## 问题摘要 / ## 分类 / ## 关键词 / ## 元数据
{HTML内容转换后的Markdown}
<!-- 文档主题:{title} Knowledge No: {knowledge_no} -->
```

末尾的 HTML 注释是有意为之，目的是在文档被切片后各片段仍保留文档主题上下文。

### 摄入流程
爬取网页 → HTML 清洗（去除 JS/CSS/广告）→ 转 Markdown → 文本分块（chunk_size=3000, overlap=300, 按 `\n##` → `\n**` → `\n\n` 等层级分割）→ 嵌入向量化 → Chroma 存储

### 检索流程（两路并行）
1. **一路**: 向量语义检索（Chroma L2 相似度，TOP 5）
2. **二路**: 标题关键词匹配（jieba 分词 + 字符交集，TOP 20）→ 标题嵌入相似度精排（TOP 5）→ 长文档重新分片召回（TOP 3/文档）
3. 合并两路结果 → 基于内容哈希去重 → 余弦相似度重排序 → 阈值过滤（DYNAMIC_THRESHOLD=0.5）或 top_k 截断
4. 最终文档送入 LLM 生成回答

**重要**：二路检索的标题扫描目录固定为 `settings.CRAWL_OUTPUT_DIR`（爬虫输出目录）。通过 API 上传的文件在完成向量化后临时文件即被删除，因此上传的文件**仅**可被一路向量检索发现，不参与二路标题匹配。

## 大小文档的差异化处理

摄入和检索对大文档（> CHUNK_SIZE）与小文档的处理逻辑不同，这是跨多个文件的核心设计：

- **摄入时**（`ingestion_service.py`）：大文档分块后，每个 chunk 的 `page_content` 会加上 `主题：{title}\n\n内容：{chunk}` 前缀，metadata 中带 `chunk_index`；小文档保持原始内容，无前缀、无 `chunk_index`
- **二路检索时**（`retrieval_service.py._retrieval_long_content_split_by_similarity`）：对长文档重新分片召回，生成的 chunk 同时带有 `chunk_index` 和 `score`
- **重排序时**（`retrieval_service.py._rerank`）：通过 `chunk_index + score` 是否同时存在来区分——二路长文档分片直接使用已有 score，其余文档（Chroma 返回的大小文档、二路短文档）重新计算余弦相似度

## 文件命名与标题提取

文件命名格式 `{前缀}_{实际标题}.md` 贯穿整个系统：
- 爬虫生成：`{编号:04d}_{清洗后标题}.md`（如 `0001_如何安装系统.md`）
- API 上传：`{uuid.hex}_{原始文件名}`（如 `a1b2c3..._{用户文件名}.md`）
- `FileUtils.extract_filename()` 按 `_` 分割提取第一个 `_` 之后的部分作为标题（去除扩展名），该标题用于摄入时的 metadata 和检索时的关键词匹配

## 关键约定

- **两个独立后端**：`knowledge` 和 `consultant` 各有独立的 `setup.py`、`requirements.txt`、`.env`，互不共享依赖
- **后端工作目录**：两个模块的运行工作目录分别为 `backend/knowledge/` 和 `backend/consultant/`，因为模块内 import 使用相对包路径（如 `from config.settings import settings`），不使用绝对路径
- **后端 import 风格**：统一使用相对包路径，不使用 `from backend.knowledge.xxx` 绝对路径
- **knowledge 配置**：环境变量模板位于 `backend/knowledge/.env.example`，必需项：`API_KEY`、`BASE_URL`、`MODEL`、`EMBEDDING_MODEL`、`KNOWLEDGE_BASE_URL`；接口为 OpenAI 兼容接口
- **consultant 配置**：环境变量模板位于 `backend/consultant/.env.example`，必须配置 `SF_API_KEY` 或 `AL_BAILIAN_API_KEY` 之一，否则 `settings` 初始化时抛出异常
- 前端环境变量通过 `front/.env` 配置，使用 `VITE_` 前缀。可配置项：`VITE_PORT`、`VITE_API_TARGET`、`VITE_API_BASE_PATH`
- 爬取文件命名格式: `{编号:04d}_{清洗后的标题}.md`，标题最长 50 字符；爬取编号范围在 `crawl_cli.py` 的 `range()` 中硬编码，每次爬取前需手动修改
- 代码注释和文档使用简体中文