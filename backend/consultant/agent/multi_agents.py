from agents import Agent, ModelSettings, Runner, RunConfig
from agents.mcp import MCPServerStreamableHttp

from config.settings import settings
from infra.ai.ai_client import al_chat_completions
from infra.logging.logger import log
from infra.tools.local.map_navigation import search_coordinate_source, navigation_sites
from infra.tools.local.retrieval_knowledge import retrieval_knowledge
from infra.tools.mcp.mcp_client import web_search_mcp, baidu_map_mcp
from utils.file_utils import load_prompt

consult_agent = Agent(
    name="consult_agent",
    instructions=load_prompt(settings.PROMPTS_FILE_DIR + "/consult_agent.md"),
    model=al_chat_completions,
    tools=[retrieval_knowledge],
    mcp_servers=[web_search_mcp],
    model_settings=ModelSettings(
        temperature=0
    )
)

navigation_agent = Agent(
    name="navigation_agent",
    instructions=load_prompt(settings.PROMPTS_FILE_DIR + "/navigation_agent.md"),
    model=al_chat_completions,
    tools=[search_coordinate_source, navigation_sites],
    mcp_servers=[baidu_map_mcp],
    model_settings=ModelSettings(
        temperature=0
    )
)


async def call_agent(agent, mcp_instance: MCPServerStreamableHttp, query: str):
    connected = False

    try:
        await mcp_instance.connect()
        connected = True
        log.info(f"连接已建立")

        tools = await mcp_instance.list_tools()
        log.info(f"MCP工具列表: {[tool.name for tool in tools]}")

        result = await Runner.run(
            starting_agent=agent,
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
    except Exception as e:
        log.error(f"调用 Agent 过程中发生未预期的异常: {e}")
        raise RuntimeError(
            f"调用 Agent 过程中发生未预期的异常: {e}"
        ) from e
    finally:
        if connected:
            try:
                await mcp_instance.cleanup()
                log.info(f"连接已清理")
            except Exception as cleanup_err:
                log.error(f"清理连接时发生错误: {cleanup_err}")


async def call_consult_agent(query: str):
    await call_agent(
        agent=consult_agent,
        mcp_instance=web_search_mcp,
        query=query
    )


async def call_navigation_agent(query: str):
    await call_agent(
        agent=navigation_agent,
        mcp_instance=baidu_map_mcp,
        query=query
    )


if __name__ == '__main__':
    import asyncio

    # 测试用例，覆盖提示词中所有执行路径：
    # 1. 技术问题 + 知识库有结果   → 直接基于知识库回答，无任何声明
    # 2. 技术问题 + 知识库无结果   → 降级调用 tavily_search，回答含"以下信息来自网络搜索"声明
    # 3. 闲聊 / 非技术问题         → 直接拒绝，不调用任何工具
    # 4. 业务办理类问题             → 直接拒绝，不调用任何工具
    # test_cases = [
    #     # --- 路径 1：技术问题，预期命中私域知识库 ---
    #     "电脑开机后蓝屏怎么解决？",
    #     # --- 路径 2：技术问题，预期知识库无结果，触发网络搜索 ---
    #     "MacBook M3 如何通过 Thunderbolt 外接独立显卡？",
    #     # --- 路径 3：闲聊/天气，非技术问题，预期拒绝 ---
    #     "明天北京的天气怎么样？",
    #     # --- 路径 4：业务办理，预期拒绝 ---
    #     "帮我找一下附近最近的联想授权服务站，并导航过去。",
    # ]
    #
    #
    # async def run_all():
    #     for i, query in enumerate(test_cases, 1):
    #         print(f"\n{'=' * 60}")
    #         print(f"[用例 {i}] {query}")
    #         print('=' * 60)
    #         await main(query)


    # asyncio.run(run_all())

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
        # "我想找距离重庆市万盛区万东镇新田村最近的联想服务中心",
        # --- 路径 C：苹果官方维修，验证"官方维修"关键词组合 ---
        # "附近有vivo官方维修点吗？",
        # --- 路径 D：修 MacBook，验证英文品牌 + "修[设备]"关键词 ---
        # "哪里可以修 Reno12手机？",
        # --- 路径 E：指定名称（小米之家旗舰店），预期未找到时推荐同品牌最近点 ---
        # "帮我找一下附近的小米之家旗舰店，我要换屏",
        # --- 路径 F：技术问题，预期被拒绝，不调用工具 ---
        # "电脑开机后蓝屏怎么解决？",
        # --- 路径 G：闲聊/天气，预期被拒绝，不调用工具 ---
        # "明天北京天气怎么样？",
        # --- 路径 H：非服务站导航（商场），预期被拒绝，不调用工具 ---
        # "帮我导航到附近的购物中心",
    ]


    async def run_all():
        for i, query in enumerate(test_cases, 1):
            print(f"\n{'=' * 60}")
            print(f"[用例 {i}] {query}")
            print('=' * 60)
            await call_navigation_agent(query)


    asyncio.run(run_all())


