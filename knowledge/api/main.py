import asyncio
import logging
import os

import uvicorn
from fastapi import FastAPI

from api.router import router

# 日志打印
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(root_path="/smart/nexus/knowledge", title="Knowledge API")

app.include_router(router=router)

if __name__ == '__main__':
    try:
        # 端口从环境变量 APP_PORT 读取，默认 8000
        port = int(os.environ.get('APP_PORT', 8000))
        # 直接调用 asyncio.run(server.serve()) 避免 uvicorn.run() 传递 loop_factory 参数
        server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=port))
        asyncio.run(server.serve())
    except KeyboardInterrupt as e:
        logger.error(f"服务被中断: {e}")
    except Exception as e:
        logger.error(f"服务启动失败: {e}")

