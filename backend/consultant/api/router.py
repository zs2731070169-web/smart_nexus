from fastapi import APIRouter, Request, Query
from starlette.responses import StreamingResponse, JSONResponse, Response

from infra.logging.logger import log
from schema.request import ChatRequest, LoginRequest, CodeRequest
from schema.response import ChatHistoryResp, LoginResp, CodeResp, SystemResp, LogoutResp, DelHistoryResp
from service.agent_service import agent_service
from service.login_service import login_service
from service.session_service import session_service

router = APIRouter(prefix="/consultant")


def _get_client_ip(request: Request) -> str:
    """从请求中提取客户端真实 IP，优先级：X-Forwarded-For > X-Real-IP > 直连 IP"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # 从请求链路的ip列表里获取第一个ip（用户真实的原始ip）
        ip = forwarded_for.split(",")[0].strip()
        log.info(f"从 X-Forwarded-For 获取到客户端 IP: {ip}，原始 X-Forwarded-For 头: {forwarded_for}")
        return ip

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        # 获取上一跳ip，如果是用户直连就是用户真实ip
        ip = real_ip.strip()
        log.info(f"从 X-Real-IP 获取到客户端 IP: {ip}，原始 X-Real-IP 头: {real_ip}")
        return ip

    # 获取直接访问FastAPI进程的那个客户端的ip（本地：127.0.0.1，服务器：内网ip）
    ip = request.client.host if request.client else ""
    log.info(f"从 request.client 直接获取到客户端 IP: {ip}")
    return ip


def _ensure_user_id(request: Request) -> Response:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        log.warning("请求中缺少 user_id，用户身份缺失，请求无法继续处理")
        return JSONResponse(
            status_code=401,
            content=SystemResp(status="401", message="用户身份缺失，请重新登录").model_dump()
        )
    return user_id


@router.post("/code", response_model=CodeResp)
async def code(code_request: CodeRequest) -> CodeResp:
    """
    用户获取验证码
    :param code_request:
    :return:
    """
    try:
        log.info(f"用户获取验证码接口被调用，获取验证码请求参数：{code_request}")
        code = await login_service.get_code(code_request.user_phone)
        return CodeResp(code=code)
    except Exception as e:
        log.error(f"用户获取验证码发生异常，获取验证码请求参数：{code_request}，异常信息：{str(e)}")
        return CodeResp(status="500", message=str(e) or "获取验证码出现系统错误")


@router.post("/login", response_model=LoginResp)
async def login(login_request: LoginRequest) -> LoginResp:
    """
    用户登录，模拟手机号码和验证码登录
    :param login_request:
    :return:
    """
    try:
        log.info(f"用户登录接口被调用，登录请求参数：{login_request}")
        user_phone = login_request.user_phone
        auth_token = await login_service.user_login(user_phone, login_request.code)
        log.info(f"用户登录成功，手机号: {user_phone}，auth_token: {auth_token}")
        return LoginResp(auth_token=auth_token)
    except Exception as e:
        log.error(f"用户登录发生异常，登录请求参数：{login_request}，异常信息：{str(e)}")
        return LoginResp(status="500", message=str(e) or "用户登录失败, 请稍后再试...")


@router.delete("/logout", response_model=LogoutResp)
async def logout(request: Request) -> LogoutResp:
    """
    注销登录
    :param request:
    :return:/clear
    """
    user_id = _ensure_user_id(request)
    log.info(f"用户注销接口被调用，用户ID: {user_id}")
    try:
        await login_service.user_logout(user_id)
        return LogoutResp()
    except Exception as e:
        log.error(f"用户注销发生异常，用户ID: {user_id}，原因：{str(e)}")
        return LogoutResp(message="用户注销失败, 请稍后再试...", status="500")


@router.post("/chat")
async def consultant(chat_request: ChatRequest, request: Request) -> StreamingResponse:
    """
    处理用户咨询对话接口
    :param request:
    :param chat_request:
    :return:
    """
    user_id = _ensure_user_id(request)
    query = chat_request.query
    session_id = chat_request.session_id
    ip = _get_client_ip(request)

    log.info(f"用户咨询对话接口被调用，用户ID: {user_id}，会话ID: {session_id}，用户问题: {query}，用户ip：{ip}")

    # 流式返回回复消息
    async_generator = agent_service.stream_messages(query, user_id, session_id, ip)

    # 通过sse推送流式消息
    return StreamingResponse(
        content=async_generator,
        media_type="text/event-stream"
    )


@router.post("/query_chat_history", response_model=ChatHistoryResp)
async def query_chat_history_list(request: Request) -> ChatHistoryResp:
    """
    查询用户历史会话列表接口
    :param request:
    :return:
    """
    user_id = _ensure_user_id(request)
    log.info(f"查询用户历史会话列表接口被调用，用户ID: {user_id}")
    try:
        chat_history_list = session_service.get_history_list(user_id)
        log.info(f"查询用户历史会话列表成功，用户ID: {user_id}，历史会话数量: {len(chat_history_list)}")
        return ChatHistoryResp(
            chat_history_list=chat_history_list
        )
    except Exception as e:
        log.warning(f"查询用户历史会话列表发生异常，用户ID: {user_id}，异常信息: {str(e)}")
        return ChatHistoryResp(
            status="500",
            message="查询用户历史会话出现系统错误",
            chat_history_list=[]
        )


@router.delete("/delete_chat_history", response_model=DelHistoryResp)
async def del_chat_history(
        request: Request,
        session_id: str = Query(..., description="会话ID")
) -> DelHistoryResp:
    user_id = _ensure_user_id(request)
    try:
        log.info(f"删除用户历史会话接口被调用，用户ID: {user_id}，会话ID: {session_id}")
        session_service.del_chat_history(user_id, session_id)
        return DelHistoryResp()
    except Exception as e:
        log.warning(f"删除用户历史会话发生异常，用户ID: {user_id}，会话ID: {session_id}，异常信息: {str(e)}")
        return DelHistoryResp(status="500", message="删除历史消息失败")
