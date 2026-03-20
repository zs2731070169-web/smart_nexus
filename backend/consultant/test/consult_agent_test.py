from agents import Runner, RunConfig

from agent.node_agents import consult_agent
from infra.logging.logger import log
from infra.tools.mcp.mcp_client import web_search_mcp


async def call_agent(query: str):
    tools = await web_search_mcp.list_tools()
    log.info(f"MCP工具列表: {[tool.name for tool in tools]}")

    result = await Runner.run(
        starting_agent=consult_agent,
        input=query,
        # 不上传日志到OpenAI官方服务器，解决401问题
        run_config=RunConfig(tracing_disabled=True)
    )

    # 打印调用的工具状态
    run_items = result.new_items
    for item in run_items:
        if item.type == "tool_call_item":
            raw = item.raw_item
            log.info(f"调用工具: {raw.name}，参数: {raw.arguments}")
        if item.type == "tool_call_output_item":
            log.info(f"工具调用结果: {item.output}")

    # 打印是最后结果
    log.info(f"Agent 执行完成，结果: {result.final_output}")


async def run_all():
    # 测试用例，覆盖提示词中所有执行路径：
    # 1. 技术问题 + 知识库有结果   → 直接基于知识库回答，无任何声明
    # 2. 技术问题 + 知识库无结果   → 降级调用 tavily_search，回答含"以下信息来自网络搜索"声明
    # 3. 闲聊 / 非技术问题         → 直接拒绝，不调用任何工具
    # 4. 业务办理类问题             → 直接拒绝，不调用任何工具
    test_cases = [
        # --- 路径 1：技术问题，预期命中私域知识库 ---
        "电脑开机后蓝屏怎么解决？",
        # --- 路径 2：技术问题，预期知识库无结果，触发网络搜索 ---
        "MacBook M3 如何通过 Thunderbolt 外接独立显卡？",
        # --- 路径 3：闲聊/天气，非技术问题，预期拒绝 ---
        "明天北京的天气怎么样？",
        # --- 路径 4：业务办理，预期拒绝 ---
        "帮我找一下附近最近的联想授权服务站，并导航过去。",
    ]

    connected = False
    try:
        await web_search_mcp.connect()
        connected = True
        log.info(f"连接已建立")
        for i, query in enumerate(test_cases, 1):
            log.info(f"\n{'=' * 60}")
            log.info(f"[用例 {i}] {query}")
            log.info('=' * 60)
            await call_agent(query)
    except Exception as e:
        log.error(f"调用 Agent 过程中发生未预期的异常: {e}")
        raise RuntimeError(
            f"调用 Agent 过程中发生未预期的异常: {e}"
        ) from e
    finally:
        if connected:
            try:
                await web_search_mcp.cleanup()
                log.info(f"连接已清理")
            except Exception as cleanup_err:
                log.error(f"清理连接时发生错误: {cleanup_err}")


if __name__ == '__main__':
    import asyncio
    asyncio.run(run_all())
