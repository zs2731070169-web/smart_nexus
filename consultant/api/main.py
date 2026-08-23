import asyncio
import os
from contextlib import asynccontextmanager

import anyio
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from api.router import router
from infra.logging.logger import log
from infra.middleware.login_auth import AuthTokenMiddleware
from infra.client.mcp_client import manage_connections


# 初始化MCP连接
@asynccontextmanager
async def mcp_lifespan(app: FastAPI):
    # MCP 连接的建立/探活/重连/关闭全部收拢在管理任务内完成：
    # anyio cancel scope 与任务绑定，跨任务 enter/exit 会取消原任务并使会话失效
    first_round_done = asyncio.Event()
    init_error = []
    manager_task = asyncio.create_task(
        manage_connections(first_round_done=first_round_done, init_error=init_error)
    )

    # 等待首轮连接结束（成功/失败都会 set）
    await first_round_done.wait()
    if init_error:
        # 等管理任务完成收尾清理，并以其异常中止服务启动（保持"任一 MCP 失败即不启动"语义）
        await manager_task

    try:
        yield
    finally:
        # 取消管理任务，由其在内部统一关闭全部 MCP 连接（同任务内 exit，安全）
        manager_task.cancel()
        try:
            await manager_task
            log.info("MCP心跳任务已停止")
        except asyncio.CancelledError:
            log.info("MCP心跳任务已停止")
        except BaseException as e:
            log.error(f"MCP连接关闭时发生异常: {e}")


# 创建fastapi实例
app = FastAPI(title="售后综合智能服务",
              description="对用户的技术售后进行智能咨询，提供线下维修站推荐、维修方案建议等服务",
              lifespan=mcp_lifespan,
              version="1.0",
              root_path="/smart/nexus")

# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 鉴权
app.add_middleware(AuthTokenMiddleware)

# 路由
app.include_router(router)

if __name__ == '__main__':
    try:
        # 加载.env
        load_dotenv()
        config = uvicorn.Config(
            app,
            host=os.environ.get("APP_HOST", "0.0.0.0"),
            port=int(os.environ.get('APP_PORT', 8001))
        )
        server = uvicorn.Server(config)
        # 用 anyio.run 替代 asyncio.run，保证整个运行时在 anyio 框架内，
        # cancel scope 异常在统一上下文中处理，不会泄漏到 asyncio 层
        anyio.run(server.serve, None)
    except KeyboardInterrupt:
        log.error("服务器被用户中断，正在关闭...")
    except Exception as e:
        log.error(f"服务器发生未预期的异常: {e}")
