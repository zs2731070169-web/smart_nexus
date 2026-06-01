import json
from typing import Any

from agents import Agent, FunctionTool, Runner, RunConfig

from constants.enums import RouteStatus
from infra.logging.logger import log


async def _run_sub_agent(agent, query: str, *, label: str) -> str:
    """
    统一的子 agent 执行流程：日志 → Runner.run → 抽取工具调用 → 构造结构化返回体
    """
    try:
        log.info(f"路由到{label}，处理用户问题: {query}")

        # 执行subagent
        run_result = await Runner.run(
            starting_agent=agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True)
        )

        summary = run_result.final_output or ""
        # 抽取子agent工具参数
        tool_calls = _extract_tool_calls(run_result)
        log.info(f"{label}运行完成，工具调用: {tool_calls}，结果长度: {len(summary)}")

        return _build_envelope(status=RouteStatus.SUCCESS, summary=summary, tool_calls=tool_calls)
    except Exception as e:
        log.error(f"运行{label}过程中发生未预期的异常: {e}")
        return _build_envelope(
            status=RouteStatus.ERROR,
            error_message=f"{label}执行异常: {e}"
        )


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


class AgentRouterRegistry:
    """子 agent 路由注册器：传入 agent 实例 + 描述，自动构造路由 function_tool."""

    def __init__(self) -> None:
        self._routes: list[FunctionTool] = []

    def register(self, agent: Agent, description: str) -> None:
        async def on_invoke(_ctx, args_json: str) -> str:
            # 协调agent传递给子agent的查询/参数
            query = json.loads(args_json or "{}").get("query", "")
            # 执行subagent
            return await _run_sub_agent(agent, query, label=agent.name)

        self._routes.append(FunctionTool(
            name=f"route_{agent.name}",
            description=description,
            params_json_schema={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "用户问题"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            # 当协调 LLM 需要触发该 tool 的时候才进行回调
            on_invoke_tool=on_invoke,
        ))

    def routes(self) -> list[FunctionTool]:
        return list(self._routes)


agent_router_registry = AgentRouterRegistry()
