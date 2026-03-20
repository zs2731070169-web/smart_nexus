from contextlib import AsyncExitStack

from infra.logging.logger import log
from agent.agent_router import route_consult_agent, route_navigation_agent
from infra.tools.mcp.mcp_client import web_search_mcp, baidu_map_mcp


async def test_run_consult_agent(query: str):
    async with AsyncExitStack() as stack:
        # 交给AsyncExitStack自动管理MCP连接和关闭
        await stack.enter_async_context(cm=web_search_mcp)
        consult_run_result = await route_consult_agent(query)
        log.info(f"测试完成，售后咨询专家结果: {consult_run_result}")


async def test_run_navigation_agent(query: str):
    async with AsyncExitStack() as stack:
        # 交给AsyncExitStack自动管理MCP连接和关闭
        await stack.enter_async_context(cm=baidu_map_mcp)
        navigation_run_result = await route_navigation_agent(query)
        log.info(f"测试完成，服务站导航咨询专家结果: {navigation_run_result}")


if __name__ == '__main__':
    import asyncio

    # 测试售后咨询专家，覆盖提示词中所有执行路径：
    # 1. 技术问题 + 知识库有结果   → 直接基于知识库回答，无任何声明
    # 2. 技术问题 + 知识库无结果   → 降级调用 tavily_search，回答含"以下信息来自网络搜索"声明
    # 3. 闲聊 / 非技术问题         → 直接拒绝，不调用任何工具
    # 4. 业务办理类问题             → 直接拒绝，不调用任何工具
    # test_cases = [
    # --- 路径 1：技术问题，预期命中私域知识库 ---
    # "电脑开机后蓝屏怎么解决？",
    # --- 路径 2：技术问题，预期知识库无结果，触发网络搜索 ---
    # "MacBook M3 如何通过 Thunderbolt 外接独立显卡？",
    # --- 路径 3：闲聊 / 非技术问题 ---
    # "今天天气怎么样？",
    # --- 路径 4：业务办理类问题 ---
    # "我想预约一下手机维修服务"
    # ]

    # for test_query in test_cases:
    #     asyncio.run(test_run_consult_agent(test_query))

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


    async def run_all():
        for i, query in enumerate(test_cases, 1):
            print(f"\n{'=' * 60}")
            print(f"[用例 {i}] {query}")
            print('=' * 60)
            await test_run_navigation_agent(query)


    asyncio.run(run_all())
