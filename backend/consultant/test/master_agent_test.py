from agents import Runner, RunConfig, ToolCallItem, ToolCallOutputItem
from contextlib import AsyncExitStack

from agent.master_agent import coordination_agent
from infra.logging.logger import log
from infra.tools.mcp.mcp_client import web_search_mcp, baidu_map_mcp

if __name__ == '__main__':
    import asyncio
    import time
    from dataclasses import dataclass
    from typing import List, Optional


    @dataclass
    class AgentTestCase:
        """单个测试用例定义"""
        id: int
        category: str  # 分类名称
        query: str  # 发给 coordination_agent 的问题
        expected_tools: List[str]  # 期望调用的工具列表（顺序敏感），[] 表示不调用任何工具
        description: str  # 用例说明，解释期望行为的原因


    @dataclass
    class AgentTestResult:
        """单个测试用例的执行结果"""
        case: AgentTestCase
        actual_tools: List[str]  # 实际被调用的工具列表（按调用顺序）
        final_output: str  # agent 最终输出
        passed: bool  # 是否通过
        error: Optional[str]  # 执行异常信息
        duration_ms: int  # 耗时（毫秒）
        retry_count: int = 0  # 实际重试次数（0 表示首次成功，未重试）


    # ══════════════════════════════════════════════════════════════════
    # 测试用例定义（共 17 个，覆盖 coordination_agent.md 所有场景）
    # ══════════════════════════════════════════════════════════════════
    TEST_CASES: List[AgentTestCase] = [

        # ── 分类1：单一技术咨询任务（期望只调用 consult_agent）─────────────────
        AgentTestCase(
            1, "单一技术咨询",
            "电脑开机后蓝屏怎么解决？",
            ["route_consult_agent"],
            "故障诊断属于技术咨询，只应调用 route_consult_agent，禁止主动附加导航任务"
        ),
        AgentTestCase(
            2, "单一技术咨询",
            "联想笔记本WiFi经常断连是什么原因？",
            ["route_consult_agent"],
            "网络故障排查属于技术咨询，只调用 route_consult_agent"
        ),
        AgentTestCase(
            3, "单一技术咨询",
            "打开浏览器后网页图片显示错乱怎么回事？",
            ["route_consult_agent"],
            "显示问题属于技术咨询，只调用 route_consult_agent"
        ),

        # ── 分类2：单一导航查询任务（期望只调用 navigation_agent）────────────────
        AgentTestCase(
            4, "单一导航查询",
            "哪里有联想电脑售后？",
            ["route_navigation_agent"],
            "服务站查询属于导航场景，只应调用 route_navigation_agent，不应附加技术咨询"
        ),
        AgentTestCase(
            5, "单一导航查询",
            "附近有小米之家售后店吗？",
            ["route_navigation_agent"],
            "服务站查询属于导航场景，只调用 route_navigation_agent"
        ),
        AgentTestCase(
            6, "单一导航查询",
            "帮我找最近的华为授权维修中心",
            ["route_navigation_agent"],
            "维修中心导航属于导航场景，只调用 route_navigation_agent"
        ),

        # ── 分类3：多步任务（依次调用 consult_agent → navigation_agent）──────────
        AgentTestCase(
            7, "多步任务",
            "小米手机掉电很快怎么办？帮我顺便找下附近的小米之家售后店",
            ["route_consult_agent", "route_navigation_agent"],
            "用户明确两个任务：技术+导航，应按顺序依次调用两个工具"
        ),
        AgentTestCase(
            8, "多步任务（条件性）",
            "开机没反应怎么办？如果解决不了，找维修站",
            ["route_consult_agent", "route_navigation_agent"],
            "用户明确提到两个任务（技术排查+找维修站），提示词示例3，全部处理"
        ),
        AgentTestCase(
            9, "多步任务",
            "联想电脑如何升级操作系统版本？另外帮我找附近的联想售后站",
            ["route_consult_agent", "route_navigation_agent"],
            "技术咨询+导航，用户在一条消息里明确两个需求，按顺序调用"
        ),

        # ── 分类4：任务完整性——不推测额外任务（核心原则验证）──────────────────────
        AgentTestCase(
            10, "不过度推测（技术）",
            "开机后无任何反应",
            ["route_consult_agent"],
            "提示词示例4：只有技术问题，不应因'可能需要维修'而主动附加导航任务"
        ),
        AgentTestCase(
            11, "不过度推测（导航）",
            "oppo线下售后店在哪里",
            ["route_navigation_agent"],
            "只有导航需求，不应因'用户可能有技术问题'而主动附加技术咨询"
        ),

        # ── 分类5：超出范围——不调用任何工具，直接回复拒绝语 ──────────────────────
        AgentTestCase(
            12, "超出范围（天气闲聊）",
            "今天北京的天气怎么样？",
            [],
            "天气属于无关闲聊，直接回复拒绝语，不调用任何工具"
        ),
        AgentTestCase(
            13, "超出范围（娱乐类）",
            "帮我讲一个笑话",
            [],
            "娱乐请求与售后无关，直接回复拒绝语，不调用任何工具"
        ),
        AgentTestCase(
            14, "超出范围（股票金融）",
            "最近股票行情怎么样？",
            [],
            "金融资讯与售后无关，直接回复拒绝语，不调用任何工具"
        ),
        AgentTestCase(
            15, "超出范围（非官方服务站导航）",
            "帮我导航到附近的购物中心",
            [],
            "购物中心非官方售后服务站，直接回复拒绝语，不调用任何工具"
        ),
        AgentTestCase(
            16, "超出范围（新闻资讯）",
            "帮我看看今天有什么科技新闻",
            [],
            "新闻资讯与售后无关，直接回复拒绝语，不调用任何工具"
        ),

        # ── 分类6：特殊情况 ────────────────────────────────────────────────────
        # AgentTestCase(
        #     17, "特殊情况（历史查询）",
        #     "我刚才问了什么问题？",
        #     [],
        #     "对话历史查询，不调用任何工具，直接基于上下文回答（无历史则说明）"
        # ),
    ]


    # ══════════════════════════════════════════════════════════════════
    # 测试执行逻辑
    # ══════════════════════════════════════════════════════════════════

    async def run_single_test(tc: AgentTestCase) -> AgentTestResult:
        """运行单个测试用例，出现异常时休眠 1000ms 后重试，最多重试 3 次"""
        MAX_RETRIES = 3
        retry_count = 0
        start = time.time()

        while True:
            # 每次尝试前重置本轮收集的数据
            actual_tools = []
            final_output = ""
            error = None

            try:
                run_result = Runner.run_streamed(
                    starting_agent=coordination_agent,
                    input=tc.query,
                    run_config=RunConfig(tracing_disabled=True)
                )

                async for event in run_result.stream_events():
                    if event.type == "run_item_stream_event":
                        if event.name == "tool_called" and isinstance(event.item, ToolCallItem):
                            tool_name = event.item.raw_item.name
                            args = event.item.raw_item.arguments
                            actual_tools.append(tool_name)
                            log.info(f"[用例 {tc.id}] 工具调用: {tool_name}, 参数: {args}")
                        elif event.name == "tool_output" and isinstance(event.item, ToolCallOutputItem):
                            output = event.item.output
                            log.info(f"[用例 {tc.id}] 工具输出: {output}")

                final_output = run_result.final_output or ""
                log.info(f"[用例 {tc.id}] Agent 执行完成，最终输出: {final_output}")

                # 执行成功，跳出重试循环
                if retry_count > 0:
                    log.info(f"[用例 {tc.id}] 第 {retry_count} 次重试成功")
                break

            except Exception as e:
                error = str(e)
                log.error(f"[用例 {tc.id}] 执行异常（第 {retry_count + 1} 次尝试）: {e}")

                if retry_count < MAX_RETRIES:
                    retry_count += 1
                    log.info(f"[用例 {tc.id}] 休眠 1000ms 后进行第 {retry_count} 次重试...")
                    await asyncio.sleep(1)
                else:
                    log.error(f"[用例 {tc.id}] 已达最大重试次数（{MAX_RETRIES}），放弃重试")
                    break

        duration_ms = int((time.time() - start) * 1000)

        # 通过条件：无异常 + 实际工具调用列表（含顺序）== 期望工具列表
        passed = (error is None) and (actual_tools == tc.expected_tools)

        return AgentTestResult(
            case=tc,
            actual_tools=actual_tools,
            final_output=final_output,
            passed=passed,
            error=error,
            duration_ms=duration_ms,
            retry_count=retry_count,
        )


    async def run_all_tests():
        results: List[AgentTestResult] = []
        total = len(TEST_CASES)

        log.info(f"\n{'=' * 70}")
        log.info(f"  Coordination Agent 测试套件  共 {total} 个用例")
        log.info(f"{'=' * 70}")

        async with AsyncExitStack() as stack:
            await stack.enter_async_context(web_search_mcp)
            connection_succeeded = False
            try:
                await baidu_map_mcp.connect()
                connection_succeeded = True
                for tc in TEST_CASES:
                    log.info(f"\n[{tc.id:02d}/{total}] 分类：{tc.category}")
                    log.info(f"  问题     : {tc.query}")
                    log.info(f"  期望工具 : {tc.expected_tools if tc.expected_tools else '(不调用任何工具)'}")

                    result = await run_single_test(tc)
                    results.append(result)

                    status = "✅ PASS" if result.passed else "❌ FAIL"
                    retry_tag = f"（重试 {result.retry_count} 次后成功）" if result.passed and result.retry_count > 0 else ""
                    log.info(f"  实际工具 : {result.actual_tools if result.actual_tools else '(未调用任何工具)'}")
                    log.info(f"  状态     : {status}{retry_tag}  耗时: {result.duration_ms}ms")
                    if result.error:
                        log.info(f"  异常     : {result.error}")
            finally:
                if connection_succeeded:
                    await baidu_map_mcp.cleanup()

        # ══════════════════════════════════════════════════════════════
        # 生成测试报告
        # ══════════════════════════════════════════════════════════════
        passed_count = sum(1 for r in results if r.passed)
        failed_count = total - passed_count
        total_ms = sum(r.duration_ms for r in results)
        pass_rate = passed_count / total * 100

        log.info(f"\n{'=' * 70}")
        log.info(f"  COORDINATION AGENT 测试报告")
        log.info(f"{'=' * 70}")
        retried_count = sum(1 for r in results if r.retry_count > 0)
        retried_success = sum(1 for r in results if r.retry_count > 0 and r.passed)

        log.info(f"  总用例数 : {total}")
        log.info(f"  通  过   : {passed_count}  ({pass_rate:.1f}%)")
        log.info(f"  失  败   : {failed_count}")
        log.info(f"  有重试   : {retried_count}（其中重试成功 {retried_success} 个）")
        log.info(f"  总耗时   : {total_ms}ms  ({total_ms / 1000:.1f}s)")
        log.info(f"  平均耗时 : {total_ms // total}ms / 用例")
        log.info(f"{'─' * 70}")

        # 按分类统计
        cat_stats: dict = {}
        for r in results:
            # 去掉括号内容，只取主分类名
            cat_key = r.case.category.split("（")[0]
            if cat_key not in cat_stats:
                cat_stats[cat_key] = {"pass": 0, "fail": 0, "count": 0}
            cat_stats[cat_key]["count"] += 1
            if r.passed:
                cat_stats[cat_key]["pass"] += 1
            else:
                cat_stats[cat_key]["fail"] += 1

        log.info(f"  {'分类':<28} {'总数':>4} {'通过':>4} {'失败':>4}")
        log.info(f"  {'─' * 46}")
        for cat, stat in cat_stats.items():
            mark = "✅" if stat["fail"] == 0 else "❌"
            log.info(f"  {mark} {cat:<26} {stat['count']:>4} {stat['pass']:>4} {stat['fail']:>4}")

        log.info(f"{'─' * 70}")

        # 失败用例详情
        failed = [r for r in results if not r.passed]
        if failed:
            log.info(f"\n  ❌ 失败用例详情（共 {len(failed)} 个）")
            log.info(f"  {'─' * 66}")
            for r in failed:
                log.info(f"\n  [{r.case.id:02d}] 问题: {r.case.query}")
                log.info(f"       分类  : {r.case.category}")
                log.info(f"       期望  : {r.case.expected_tools if r.case.expected_tools else '(无工具)'}")
                log.info(f"       实际  : {r.actual_tools if r.actual_tools else '(无工具)'}")
                log.info(f"       重试  : {r.retry_count} 次")
                log.info(f"       说明  : {r.case.description}")
                if r.error:
                    log.info(f"       异常  : {r.error}")
        else:
            log.info(f"\n  🎉 所有 {total} 个用例全部通过！")

        log.info(f"\n{'=' * 70}\n")


    asyncio.run(run_all_tests())