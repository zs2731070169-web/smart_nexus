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
from infra.tools.mcp.mcp_client import connect, disconnect, heartbeat


# 初始化MCP连接
@asynccontextmanager
async def mcp_lifespan(app: FastAPI):
    try:
        await connect()  # 启动服务器的时候创建连接
    except asyncio.CancelledError:
        log.error("MCP初始化被anyio cancel scope取消，服务启动中止")
        raise
    except Exception as e:
        log.error(f"MCP初始化失败，服务将在无MCP工具状态下运行: {e}")

    # 启动MCP心跳任务（后台运行，定期探活并自动重连）
    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        yield
    finally:
        # 停止心跳任务（发送异步任务取消信号）
        heartbeat_task.cancel()
        try:
            # 等待异步任务真正结束
            await heartbeat_task
            log.info("MCP心跳任务已停止")

            # 销毁服务器的时候关闭连接
            await disconnect()
        except asyncio.CancelledError:
            log.warning("MCP心跳任务异常停止...")
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
