from agents import Runner, RunConfig

from agent.node_agents import navigation_agent
from infra.logging.logger import log
from infra.tools.mcp.mcp_client import baidu_map_mcp


async def call_agent(query: str):
    tools = await baidu_map_mcp.list_tools()
    log.info(f"MCP工具列表: {[tool.name for tool in tools]}")

    result = await Runner.run(
        starting_agent=navigation_agent,
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
    # navigation_agent 测试用例，覆盖提示词中所有执行路径：
    #
    # ✅ 服务站流程（调用 search_coordinate_source → navigation_sites → map_uri）：
    #   路径 A：品牌 + 服务关键词（"售后"）触发，预期返回前3家服务站完整信息 + 导航链接
    #   路径 B：品牌 + 服务关键词（"服务中心"）触发，验证不同关键词均能命中
    #   路径 C：关键词"修[设备]"触发（"哪里可以修 MacBook"），验证英文品牌场景
    #   路径 D：关键词"保修/换屏"触发，验证维修动作词
    #   路径 E：指定名称可能不存在，预期推荐同品牌最近授权点并注明"未找到指定名称"
    #
    # 🚫 拒绝流程（不调用任何工具，直接返回固定回复）：
    #   路径 F：技术问题   → 回复"我仅支持位置与服务站查询……"
    #   路径 G：闲聊/无关  → 回复"我当前仅支持导航与服务站查询功能。"
    #   路径 H：非服务站导航（商场/学校等）→ 回复"我当前仅支持官方服务站的查询与导航。"

    test_cases = [
        # --- 路径 A：小米 + "售后"，最常见服务站查询场景 ---
        "哪里有联想电脑售后？",
        # --- 路径 B：联想 + "服务中心"，验证另一品牌及关键词变体 ---
        "我想找距离重庆市万盛区万东镇新田村最近的联想服务中心",
        # --- 路径 C：苹果官方维修，验证"官方维修"关键词组合 ---
        "附近有vivo官方维修点吗？",
        # --- 路径 D：修 MacBook，验证英文品牌 + "修[设备]"关键词 ---
        "哪里可以修 Reno12手机？",
        # --- 路径 E：指定名称（小米之家旗舰店），预期未找到时推荐同品牌最近点 ---
        "帮我找一下附近的小米之家旗舰店，我要换屏",
        # --- 路径 F：技术问题，预期被拒绝，不调用工具 ---
        "电脑开机后蓝屏怎么解决？",
        # --- 路径 G：闲聊/天气，预期被拒绝，不调用工具 ---
        "明天北京天气怎么样？",
        # --- 路径 H：非服务站导航（商场），预期被拒绝，不调用工具 ---
        "帮我导航到附近的购物中心",
    ]

    connected = False
    try:
        await baidu_map_mcp.connect()
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
                await baidu_map_mcp.cleanup()
                log.info(f"连接已清理")
            except Exception as cleanup_err:
                log.error(f"清理连接时发生错误: {cleanup_err}")


if __name__ == '__main__':
    import asyncio

    asyncio.run(run_all())
