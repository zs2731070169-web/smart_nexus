import asyncio
import uuid
from typing import AsyncGenerator, AsyncIterator, Optional

from agents import Runner, RunConfig, StreamEvent

from agent.master_agent import coordination_agent
from constants.enums import RenderType, TOOL_NAME_MAPPING, AGENT_NAME_MAPPING, FinishedReason
from infra.logging.logger import log
from schema.response import StreamMessages
from service.memory_service import memory_service

MAX_TRY_COUNT = 3


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
            history_messages.append(
                {
                    "role": "user",
                    "content": query
                })

            log.info(f"加载历史消息完成，用户问题: {query}，历史消息轮数: {len(history_messages)}")

            # 流式执行协调agent，获取流式执行结果
            run_result = Runner.run_streamed(
                starting_agent=coordination_agent,  # 入口agent
                input=history_messages + [{"role": "user", "content": f"\n\n[非用户问题，用户当前ip：{ip}]"}]  if ip else [], # 模型参考上下文
                context=query,  # 明确重点关注用户当前指令
                max_turns=5,  # ReAct动作最多循环5次
                run_config=RunConfig(tracing_disabled=True)
            )

            log.info(f"协调agent执行完成，开始处理流式事件，用户问题: {query}，重试次数: {retry_count}")

            # 处理流式消息，返回异步生成器不需要await，直接返回生成器对象即可，由异步迭代器获取消息
            chunks = self._handle_streaming_event(run_result.stream_events())
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

                # 非阻塞等待 0.5 秒
                await asyncio.sleep(0.5)

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

        # 如果有异常则重试

    async def _handle_streaming_event(self, events: AsyncIterator[StreamEvent]) -> AsyncGenerator:
        """
        处理各种流式事件。
        """
        # 统计流式输出指标
        answer_chars = 0  # 回复字符数
        thinking_chars = 0  # 思考字符数
        tool_call_count = 0  # 调用工具次数
        agent_switch_count = 0  # 切换agent次数

        async for event in events:
            message = ""
            render_type = None
            # llm返回事件
            if event.type == "raw_response_event":
                # 流式返回ai的回复
                if event.data.type == "response.output_text.delta":
                    message = event.data.delta
                    render_type = RenderType.ANSWER
                    answer_chars += len(message)
                # 流式返回ai的思考过程
                elif event.data.type in ["response.reasoning_summary_text.delta", "response.reasoning_text.delta"]:
                    message = event.data.delta
                    render_type = RenderType.THINKING
                    thinking_chars += len(message)
            # agent执行事件
            elif event.type == "run_item_stream_event" and event.name == "tool_called":
                # 返回ai的工具调用项
                tool_name = event.item.raw_item.name
                log.debug(f"工具调用: {tool_name}")  # 有诊断价值但不污染 info.log
                tool_name = TOOL_NAME_MAPPING.get(tool_name, tool_name)
                message = f"正在调用工具 {tool_name} ..."
                render_type = RenderType.PROCESSING
                tool_call_count += 1
            # agent切换事件
            elif event.type == "agent_updated_stream_event":
                agent_name = event.new_agent.name
                log.debug(f"Agent 切换: {agent_name}")
                message = f"切换到 {AGENT_NAME_MAPPING.get(agent_name, agent_name)} 执行 ..."
                render_type = RenderType.PROCESSING
                agent_switch_count += 1

            if message and message.strip() and render_type and isinstance(render_type, RenderType):
                stream_messages = StreamMessages.build_processing(message, render_type)  # 构建流式消息对象
                yield "data: " + stream_messages.model_dump_json() + "\n\n"  # 流式推送消息

        # 一条汇总日志代替所有细粒度日志，既有诊断价值又不刷屏
        log.info(
            f"流式事件处理完成 | 回复: {answer_chars}字 | 思考: {thinking_chars}字 "
            f"| 工具调用: {tool_call_count}次 | Agent切换: {agent_switch_count}次"
        )

        # 执行完成，发送sse关闭消息
        yield ("data: " + StreamMessages
               .build_finished(finished_reason=FinishedReason.NORMAL)
               .model_dump_json() + "\n\n"
               )


agent_service = AgentService()
