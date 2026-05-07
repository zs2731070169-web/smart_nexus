import asyncio
from typing import AsyncGenerator, AsyncIterator, Optional

from agents import Runner, RunConfig, StreamEvent

from agent.master_agent import coordination_agent
from constants.enums import RenderType, TOOL_NAME_MAPPING, AGENT_NAME_MAPPING, FinishedReason, MAX_TRY_COUNT
from infra.logging.logger import log
from schema.response import StreamMessages
from service.memory_service import memory_service
from utils.tag_extract_utils import make_think_state, extract_think_tag, flush_think_tag


class AgentService:

    async def stream_messages(self,
                              query: str,
                              user_id: str,
                              session_id: str,
                              ip: Optional[str] = None,
                              retry_count: int = 0) -> AsyncGenerator:
        """
        流式处理对话生成的消息
        :param ip:
        :param retry_count:
        :param query:
        :param user_id:
        :param session_id:
        :return:
        """
        try:
            # 校验是否有session_id，强制要求携带，由前端生成
            if not session_id:
                raise ValueError("请求缺少会话id，无法加载历史消息，请确保 session_id 并随请求携带")

            # 加载对话到上下文
            history_messages = memory_service.load_history(user_id, session_id)

            # 将用户最新输入加入历史消息，作为agent输入的一部分
            history_messages.append({"role": "user", "content": query})

            log.info(f"加载历史消息完成，用户问题: {query}，历史消息轮数: {len(history_messages)}")

            # 流式执行协调agent，获取流式执行结果
            run_result = Runner.run_streamed(
                starting_agent=coordination_agent,  # 入口agent
                input=history_messages + [
                    {"role": "user", "content": f"\n\n[非用户问题，用户当前ip：{ip}]"}] if ip else [],  # 模型参考上下文
                context=query,  # 明确重点关注用户当前指令
                max_turns=15,  # ReAct循环：1轮约消耗2-3 turns，预留 5-7 轮 Thought→Action→Observation 余量
                run_config=RunConfig(tracing_disabled=True)
            )

            log.info(f"协调agent执行完成，开始处理流式事件，用户问题: {query}，重试次数: {retry_count}")

            # 处理流式消息，返回异步生成器不需要await，直接返回生成器对象即可，由异步迭代器获取消息
            chunks = _handle_streaming_event(run_result.stream_events())
            async for chunk in chunks:
                yield chunk

            # 保存最新的一轮对话到历史上下文
            content = run_result.final_output if run_result.final_output is not None else ""
            history_messages.append({"role": "assistant", "content": content})
            if memory_service.save_history(user_id, session_id, history_messages):
                log.info(f"对话处理完成，历史消息已保存")
        except Exception as e:
            log.error(f"处理对话流式消息过程中发生异常: {str(e)}")

            if isinstance(e, ValueError):
                yield ("data: " + StreamMessages.build_finished(
                    finished_reason=FinishedReason.EXCEPTION,
                    error_message=str(e)
                ).model_dump_json() + "\n\n")
            # 小于最大重试次数，执行重试
            elif retry_count < MAX_TRY_COUNT:
                log.info(f"正在第 {retry_count + 1} 次重试处理对话...")

                yield ("data: " + StreamMessages.build_processing(
                    data="❌处理对话过程中发生系统异常",
                    render_type=RenderType.PROCESSING
                ).model_dump_json() + "\n\n")

                yield ("data: " + StreamMessages.build_processing(
                    data="🔁重新尝试处理该对话",
                    render_type=RenderType.PROCESSING
                ).model_dump_json() + "\n\n")

                # 指数退避等待：0.5s, 1s, 2s, ...，最大 10s
                backoff_seconds = min(0.5 * (2 ** retry_count), 10)
                await asyncio.sleep(backoff_seconds)

                # 递归重试
                async for chunk in self.stream_messages(query, user_id, session_id, ip, retry_count + 1):
                    yield chunk
            # 超过最大重试次数，直接返回异常信息
            else:
                log.error(f"❌第 {retry_count} 次重试处理对话仍然失败，已达最大重试次数，停止重试")
                yield ("data: " + StreamMessages.build_finished(
                    finished_reason=FinishedReason.EXCEPTION,
                    error_message=f"❌系统异常重试执行失败，原因: {str(e)}，请稍后再试..."
                ).model_dump_json() + "\n\n")


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


agent_service = AgentService()
