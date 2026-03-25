import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from config.settings import settings
from infra.logging.logger import log
from repo.database_repo import database_repo


class AuthTokenMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        从请求头获取auth_token 并进行鉴权操作
        :param request:
        :param call_next:
        :return:
        """
        log.info("AuthTokenMiddleware: 开始进行用户凭证校验...")

        # 接口过滤
        if request.url.path in settings.WHITE_LIST:
            log.info(f"AuthTokenMiddleware: 白名单接口 {request.url.path} 跳过校验")
            return await call_next(request)

        auth_header = request.headers.get("authorization")

        log.info(f"AuthTokenMiddleware: 获取到请求头中的 authorization: {auth_header}")

        # 验证auth_token，格式是否正确
        if not auth_header or not auth_header.startswith("Bearer "):
            log.warning("AuthTokenMiddleware: 请求头中缺少 Bearer token 或格式不正确，authorization")
            return JSONResponse(status_code=401, content="缺少 Bearer token")

        token = auth_header.split(" ", 1)[1]

        try:
            # 验证token是否24h有效，得到userid 并存入 request.state，失败则抛异常
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload["user_id"]
            iat = payload.get("iat")

            # 校验token是否是当前会话的有效token(防止旧token)
            login_status = await database_repo.query_login_time(user_id)
            if not login_status:
                log.warning(f"AuthTokenMiddleware: 用户 {user_id} 没有登录记录或已登出")
                return JSONResponse(status_code=401, content="用户未登录")
            elif iat < int(login_status['login_time'].timestamp()):
                login_time = login_status['login_time']
                log.warning(f"AuthTokenMiddleware: token 已过期，登录时间: {login_time}，token 生成时间: {iat}")
                return JSONResponse(status_code=401, content="token 已过期，请重新登录")

            request.state.user_id = user_id
        except jwt.PyJWTError:
            log.warning(f"AuthTokenMiddleware: token 验证失败，token 无效或已过期")
            return JSONResponse(status_code=401, content="token 无效或已过期")

        log.info(f"AuthTokenMiddleware: token 验证成功，提取到 user_id: {request.state.user_id}")

        return await call_next(request)
