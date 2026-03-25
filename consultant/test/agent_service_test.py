import asyncio

from infra.tools.mcp.mcp_client import web_search_mcp, baidu_map_mcp
from service.agent_service import agent_service

if __name__ == '__main__':
    # ──────────────────────────────────────────────────────────────────────────
    # 单轮测试用例（覆盖不同 Agent 调用路径）
    # ──────────────────────────────────────────────────────────────────────────
    TEST_CASES = [
        # ── 技术咨询（consult_agent 路径）─────────────────────────────────────
        # {
        #     "name": "01_技术咨询_Wi-Fi连接失败",
        #     "query": "我的电脑无法连接Wi-Fi了，怎么办？",
        #     "user_id": "test_user_01",
        #     "session_id": "session_wifi",
        #     "desc": "触发 consult_agent + retrieval_knowledge 工具",
        # },
        # {
        #     "name": "02_技术咨询_蓝屏BSOD",
        #     "query": "电脑开机后出现蓝屏，错误代码 DRIVER_IRQL_NOT_LESS_OR_EQUAL，如何修复？",
        #     "user_id": "test_user_02",
        #     "session_id": "session_bsod",
        #     "desc": "触发 consult_agent + retrieval_knowledge，知识库无结果时 fallback 到 tavily_search",
        # },
        # {
        #     "name": "03_技术咨询_电池续航",
        #     "query": "我的联想笔记本电池续航越来越短，充满电只能用2小时，怎么解决？",
        #     "user_id": "test_user_03",
        #     "session_id": "session_battery",
        #     "desc": "触发 consult_agent，测试电池类问题的知识库召回",
        # },
        # {
        #     "name": "04_技术咨询_显卡驱动",
        #     "query": "系统提示显卡驱动有问题，应该怎么重新安装显卡驱动？",
        #     "user_id": "test_user_04",
        #     "session_id": "session_driver",
        #     "desc": "触发 consult_agent，可能需要 tavily_search 搜索最新驱动信息",
        # },
        # ── 导航查询（navigation_agent 路径）──────────────────────────────────
        # {
        #     "name": "05_导航查询_城市级地址",
        #     "query": "我在北京海淀区，附近有联想售后服务站吗？帮我导航过去",
        #     "user_id": "test_user_05",
        #     "session_id": "session_nav_city",
        #     "desc": "触发 navigation_agent + search_coordinate_source(geocode) + navigation_sites",
        # },
        {
            "name": "06_导航查询_详细地址",
            "query": "最近的oppo维修点在哪？",
            "user_id": "test_user_06",
            "session_id": "session_nav_detail",
            "desc": "触发 navigation_agent + 精确地址 geocode + Haversine 最近站点查询",
        },
        # {
        #     "name": "07_导航查询_无地址IP定位兜底",
        #     "query": "帮我找一下附近的联想维修站?",
        #     "user_id": "test_user_07",
        #     "session_id": "session_nav_ip",
        #     "desc": "触发 navigation_agent，无地址信息，依次尝试 IP 定位或默认坐标兜底",
        # },
        # ── 混合意图（coordination_agent 依次调度两个子 Agent）─────────────────
        # {
        #     "name": "08_混合意图_咨询加导航",
        #     "query": "我的电脑触摸板失灵了，同时帮我找一下深圳南山区最近的联想维修中心，我想去现场处理",
        #     "user_id": "test_user_08",
        #     "session_id": "session_mixed",
        #     "desc": "测试 coordination_agent 是否能依次路由 consult_agent 和 navigation_agent",
        # },
        # ── 闲聊 / 无关问题（coordination_agent 直接回答，不路由子 Agent）────────
        # {
        #     "name": "09_闲聊_非售后问题",
        #     "query": "你好，你是什么系统？能帮我做什么？",
        #     "user_id": "test_user_09",
        #     "session_id": "session_chat",
        #     "desc": "coordination_agent 直接回答，不路由子 Agent，覆盖不调用工具的分支",
        # },
    ]

    # ──────────────────────────────────────────────────────────────────────────
    # 多轮对话测试用例（同一 session 连续两轮，验证 memory_service 上下文机制）
    # ──────────────────────────────────────────────────────────────────────────
    # MULTI_TURN_CASE = {
    #     "name": "10_多轮对话_上下文追问",
    #     "turns": [
    #         {
    #             "query": "我的联想笔记本开机很慢，需要等3分钟才能进桌面",
    #             "desc": "第一轮：技术咨询",
    #         },
    #         {
    #             "query": "你说的那个方法我试过了，没有明显改善，还有别的办法吗？",
    #             "desc": "第二轮：基于上下文追问，验证历史消息被正确传递",
    #         },
    #     ],
    #     "user_id": "test_user_10",
    #     "session_id": "session_multi_turn",
    # }

    # ──────────────────────────────────────────────────────────────────────────
    # 运行控制：None 表示全部运行；填写名称列表可只运行指定用例
    # 示例：RUN_CASES = ["01_技术咨询_Wi-Fi连接失败", "05_导航查询_城市级地址"]
    # ──────────────────────────────────────────────────────────────────────────
    RUN_CASES = None


    async def _run_single(name: str, query: str, user_id: str, session_id: str, desc: str = ""):
        """运行单条测试用例并打印流式输出"""
        print(f"\n{'=' * 60}")
        print(f"[{name}]  {desc}")
        print(f"Query: {query}")
        print("=" * 60)
        async for chunk in agent_service.stream_messages(query=query, user_id=user_id, session_id=session_id, ip="156.59.13.62"):
            print(chunk, end="", flush=True)
        print()


    async def main():
        mcp_conn = False
        try:
            await web_search_mcp.connect()
            await baidu_map_mcp.connect()
            mcp_conn = True

            # 单轮测试用例
            for case in TEST_CASES:
                if RUN_CASES is None or case["name"] in RUN_CASES:
                    await _run_single(**case)

            # 多轮对话测试
            # if RUN_CASES is None or MULTI_TURN_CASE["name"] in RUN_CASES:
            #     print(f"\n{'=' * 60}")
            #     print(f"[{MULTI_TURN_CASE['name']}]  多轮对话 / memory_service 上下文验证")
            #     print("=" * 60)
            #     for i, turn in enumerate(MULTI_TURN_CASE["turns"], 1):
            #         print(f"\n--- 第 {i} 轮  {turn['desc']} ---")
            #         print(f"Query: {turn['query']}")
            #         async for chunk in agent_service.stream_messages(
            #                 query=turn["query"],
            #                 user_id=MULTI_TURN_CASE["user_id"],
            #                 session_id=MULTI_TURN_CASE["session_id"],
            #         ):
            #             print(chunk, end="", flush=True)
            #         print()

        finally:
            if mcp_conn:
                await web_search_mcp.cleanup()
                await baidu_map_mcp.cleanup()


    asyncio.run(main())
