import json
from typing import Any

from agents import Runner, RunConfig, function_tool

from agent.node_agents import consult_agent, navigation_agent
from constants.enums import RouteStatus
from infra.logging.logger import log


@function_tool
async def route_consult_agent(query: str) -> str:
    """
    **售后咨询专家**：专门负责处理用户技术售后咨询
    比如：
        电脑开机后蓝屏怎么解决？
        MacBook M3 如何通过 Thunderbolt 外接独立显卡？

    :param str query: 用户的咨询问题，可能涉及电脑、电视、手机等电子设备的技术售后问题
    :return: JSON 字符串，包含 status / summary / tool_calls 字段
    """
    return await _run_sub_agent(consult_agent, query, label="售后咨询专家")


@function_tool
async def route_navigation_agent(query: str) -> str:
    """
    **售后服务站导航专家**：专门负责处理用户关于线下售后服务站点的导航问题
    比如：
        哪里有联想电脑售后？
        附近有vivo官方维修点吗？
        帮我找一下附近的小米之家旗舰店，我要换屏

    :param str query: 用户咨询的售后站点导航问题
    :return: JSON 字符串，包含 status / summary / tool_calls 字段
    """
    return await _run_sub_agent(navigation_agent, query, label="售后服务站导航专家")


async def _run_sub_agent(agent, query: str, *, label: str) -> str:
    """
    统一的子 agent 执行流程：日志 → Runner.run → 抽取工具调用 → 构造结构化返回体
    """
    try:
        log.info(f"路由到{label}，处理用户问题: {query}")

        run_result = await Runner.run(
            starting_agent=agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True)
        )

        summary = run_result.final_output or ""
        tool_calls = _extract_tool_calls(run_result)
        log.info(f"{label}运行完成，工具调用: {tool_calls}，结果长度: {len(summary)}")

        return _build_envelope(status=RouteStatus.SUCCESS, summary=summary, tool_calls=tool_calls)
    except Exception as e:
        log.error(f"运行{label}过程中发生未预期的异常: {e}")
        return _build_envelope(
            status=RouteStatus.ERROR,
            error_message=f"{label}执行异常: {e}"
        )


def _build_envelope(status: str,
                    summary: str = "",
                    error_message: str = "",
                    tool_calls: list[str] | None = None) -> str:
    """
    构造子 agent 的结构化返回体（JSON 字符串）

    顶层 coordination_agent 通过 status 字段判断是否需要 replan，
    通过 tool_calls 看到子 agent 实际用了哪些工具，
    summary 是子 agent 的最终自然语言输出，可直接用于综合 Final Answer。
    """
    envelope: dict[str, Any] = {
        "status": status,  # success | error
        "summary": summary,
        "tool_calls": tool_calls or [],
    }
    if error_message:
        envelope["error_message"] = error_message
    return json.dumps(envelope, ensure_ascii=False)


def _extract_tool_calls(run_result) -> list[str]:
    """
    从 RunResult 中抽取子 agent 调用过的工具名，作为顶层可观察信号
    """
    tools: list[str] = []
    try:
        for item in getattr(run_result, "new_items", []) or []:
            raw = getattr(item, "raw_item", None)
            name = getattr(raw, "name", None)
            if name:
                tools.append(name)
    except Exception as e:
        log.debug(f"提取子 agent 工具调用失败: {e}")
    return tools


AGENT_ROUTER = [
    route_consult_agent,
    route_navigation_agent,
]
