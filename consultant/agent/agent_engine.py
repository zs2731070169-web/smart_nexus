import asyncio
from typing import AsyncGenerator, AsyncIterator, Optional, Tuple

from agents import Runner, RunConfig, StreamEvent

from agent.master_agent import coordination_agent
from constants.enums import RenderType, TOOL_NAME_MAPPING, AGENT_NAME_MAPPING, FinishedReason, MAX_TRY_COUNT
from infra.error import classify_llm_error, jittered_backoff
from infra.logging.logger import log
from infra.memory import MemoryManager, default_compressor
from schema.response import StreamMessages
from utils.tag_extract_utils import make_think_state, extract_think_tag, flush_think_tag


class AgentEngine:

    def __init__(self):
        # 默认装配：token 预算压缩器
        self.memory_manager = MemoryManager(compressor=default_compressor)

    async def stream_messages(self,
                              query: str,
                              user_id: str,
                              session_id: str,
                              location: Optional[Tuple[float, float]] = None,
                              retry_count: int = 0) -> AsyncGenerator:
        """
        流式处理对话生成的消息
        :param location: 前端定位 (经度, 纬度)，BD09 坐标系；导航起点信号
        :param retry_count:
        :param query:
        :param user_id:
        :param session_id:
        :return:
        """
        # 业务校验：不属于系统错误，直接终止，不进入重试流程
        if not session_id:
            yield ("data: " + StreamMessages.build_finished(
                finished_reason=FinishedReason.EXCEPTION,
                error_message="请求缺少会话id，无法加载历史消息，请确保 session_id 并随请求携带"
            ).model_dump_json() + "\n\n")
            return

        # 记录已发出的流式帧数，用于判断重试是否会导致重复内容
        chunks_sent = 0
        try:
            # 加载历史对话，并合并查询
            history_messages = self.memory_manager.load_history(user_id, session_id)
            history_messages.append({"role": "user", "content": query})
            log.info(f"加载历史消息完成，用户问题: {query}，历史消息轮数: {len(history_messages)}")

            # 透传给 agent 的附加上下文（仅本轮注入，不写入历史）：前端定位
            extra_inputs = []
            if location:
                lng, lat = location
                extra_inputs.append({
                    "role": "user",
                    "content": f"\n\n[非用户问题，用户当前位置经纬度(BD09坐标系)：经度={lng}，纬度={lat}]"
                })

            # 调用协调agent
            run_result = Runner.run_streamed(
                starting_agent=coordination_agent,
                input=history_messages + extra_inputs,
                context=query,
                max_turns=15,
                run_config=RunConfig(tracing_disabled=True)
            )
            log.info(f"协调agent执行完成，开始处理流式事件，用户问题: {query}，重试次数: {retry_count}")

            # 流式打印agent的chunk
            async for chunk in _handle_streaming_event(run_result.stream_events()):
                chunks_sent += 1
                yield chunk

        except Exception as e:
            log.error(f"处理对话流式消息过程中发生异常: {str(e)}")

            # 获取异常分类对象
            retryable, user_message = _classify_engine_error(e)

            # 允许重试且没有超过最大重试次数，就允许重试
            if retryable and chunks_sent == 0 and retry_count < MAX_TRY_COUNT:
                log.info(f"正在第 {retry_count + 1} 次重试处理对话...")
                yield ("data: " + StreamMessages.build_processing(
                    data="❌处理对话过程中发生系统异常，🔁重新尝试处理该对话",
                    render_type=RenderType.PROCESSING
                ).model_dump_json() + "\n\n")
                # 指数级退避
                await asyncio.sleep(jittered_backoff(retry_count + 1, base_delay=0.5, max_delay=10.0))
                # 递归调用agent
                async for chunk in self.stream_messages(query, user_id, session_id, location, retry_count + 1):
                    yield chunk
            else:
                # 超过最大重试次数，打印错误日志
                if retry_count >= MAX_TRY_COUNT:
                    log.error(f"❌ 重试 {retry_count} 次仍失败，已达最大重试次数，停止重试")
                # 返回错误信息
                yield ("data: " + StreamMessages.build_finished(
                    finished_reason=FinishedReason.EXCEPTION,
                    error_message=user_message
                ).model_dump_json() + "\n\n")
            # 异常路径结束，跳过 save_history ，不保留历史对话
            return

        history_messages.append({
            "role": "assistant",
            "content": run_result.final_output if run_result.final_output is not None else ""
        })
        try:
            # 保存历史对话
            if await self.memory_manager.save_history(user_id, session_id, history_messages):
                log.info(f"对话处理完成，历史消息已保存")
        except Exception as e:
            log.error(f"历史消息保存失败，本轮对话不计入上下文: {str(e)}")


async def _handle_streaming_event(events: AsyncIterator[StreamEvent]) -> AsyncGenerator:
    """
    处理各种流式事件。
    """
    # 统计流式输出指标
    answer_token = 0  # 回复字符数
    thinking_token = 0  # 思考字符数
    tool_call_count = 0  # 调用工具次数
    agent_switch_count = 0  # 切换agent次数

    def emit(items: list[tuple[RenderType, str]]):
        """
        日志指标统计; 并将待下发片段构造成消息对象，返回生成器
        :param items:
        :return:
        """
        nonlocal answer_token, thinking_token
        for render_type, message in items:
            if not (message and message.strip()):
                continue
            if render_type == RenderType.ANSWER:
                answer_token += len(message)
            elif render_type == RenderType.THINKING:
                thinking_token += len(message)
            yield "data: " + StreamMessages.build_processing(message, render_type).model_dump_json() + "\n\n"

    # 用于拆分的<think>或</think>标签，以及huf缓存初始状态
    think_state = make_think_state()

    # 收集到的待下发片段，每项是 (render_type, message)
    pending: list[tuple[RenderType, str]] = []

    async for event in events:
        pending.clear()
        # llm返回事件
        if event.type == "raw_response_event":
            # AI回复
            if event.data.type == "response.output_text.delta":
                # 拆分AI的思考与回答
                pending.extend(extract_think_tag(think_state, event.data.delta))
            # 部分模型走独立 reasoning 事件，原样按 THINKING 下发
            elif event.data.type in ["response.reasoning_summary_text.delta", "response.reasoning_text.delta"]:
                if event.data.delta:
                    pending.append((RenderType.THINKING, event.data.delta))
        # agent执行事件
        elif event.type == "run_item_stream_event" and event.name == "tool_called":
            # 切换 agent 把上一段 AI 输出"还在 buf 里等拼接的尾巴"强制刷出
            pending.extend(flush_think_tag(think_state))
            tool_name = event.item.raw_item.name
            log.debug(f"工具调用: {tool_name}")
            tool_name = TOOL_NAME_MAPPING.get(tool_name, tool_name)
            pending.append((RenderType.PROCESSING, f"正在调用工具 {tool_name} ..."))
            tool_call_count += 1
        # agent切换事件
        elif event.type == "agent_updated_stream_event":
            # 切换 agent 把上一段 AI 输出"还在 buf 里等拼接的尾巴"强制刷出
            pending.extend(flush_think_tag(think_state))
            agent_name = event.new_agent.name
            log.debug(f"Agent 切换: {agent_name}")
            pending.append(
                (RenderType.PROCESSING, f"切换到 {AGENT_NAME_MAPPING.get(agent_name, agent_name)} 执行 ..."))
            agent_switch_count += 1

        for chunk in emit(pending):
            yield chunk

    # 流结束前刷新残留的buf片段
    for chunk in emit(flush_think_tag(think_state)):
        yield chunk

    # 汇总日志
    log.info(
        f"流式事件处理完成 | 回复: {answer_token}字 | 思考: {thinking_token}字 "
        f"| 工具调用: {tool_call_count}次 | Agent切换: {agent_switch_count}次"
    )

    # 执行完成，发送sse关闭消息
    yield ("data: " + StreamMessages
           .build_finished(finished_reason=FinishedReason.NORMAL)
           .model_dump_json() + "\n\n"
           )


def _classify_engine_error(e: Exception) -> tuple[bool, str]:
    """对 agent 引擎层异常统一分类，返回 (retryable, user_message)"""
    if isinstance(e, (ValueError, TypeError, KeyError, AttributeError)):
        # 代码错误，重试无意义
        return False, str(e)
    # 其余交给分类器判断
    classified = classify_llm_error(e)
    return classified.retryable, classified.user_message


agent_engine = AgentEngine()
