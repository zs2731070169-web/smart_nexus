"""
SSE 接口压测脚本
-----------------
向 consultant /chat 接口发起 SSE 请求，覆盖所有测试用例，
汇总每条用例的耗时指标并输出统计报告。

运行方式（工作目录须为 backend/consultant/）：
    python test/sse_api_test.py
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

# ─────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────
BASE_URL = "http://127.0.0.1:8001/smart/nexus/consultant/chat"
USER_ID = "test_user_01"
SESSION_ID = "optional_session_01"
TIMEOUT = 120  # 秒，单条用例最长等待时间


# ─────────────────────────────────────────────────────────────
# 测试用例定义
# ─────────────────────────────────────────────────────────────
# 单轮测试用例
SINGLE_TURN_CASES = [
    # ── 技术咨询 ────────────────────────────────────────────
    {
        "name": "01_技术咨询_Wi-Fi连接失败",
        "category": "技术咨询",
        "query": "我的电脑无法连接Wi-Fi了，怎么办？",
    },
    {
        "name": "02_技术咨询_蓝屏BSOD",
        "category": "技术咨询",
        "query": "电脑开机后出现蓝屏，错误代码 DRIVER_IRQL_NOT_LESS_OR_EQUAL，如何修复？",
    },
    {
        "name": "03_技术咨询_电池续航",
        "category": "技术咨询",
        "query": "我的联想笔记本电池续航越来越短，充满电只能用2小时，怎么解决？",
    },
    {
        "name": "04_技术咨询_显卡驱动",
        "category": "技术咨询",
        "query": "系统提示显卡驱动有问题，应该怎么重新安装显卡驱动？",
    },
    # ── 导航查询 ────────────────────────────────────────────
    {
        "name": "05_导航查询_北京海淀区",
        "category": "导航查询",
        "query": "我在北京海淀区，附近有联想售后服务站吗？帮我导航过去",
    },
    {
        "name": "06_导航查询_上海张江",
        "category": "导航查询",
        "query": "我现在在上海市浦东新区张江高科技园区，最近的联想维修点在哪？",
    },
    {
        "name": "07_导航查询_无地址IP兜底",
        "category": "导航查询",
        "query": "帮我找一下附近的联想维修站",
    },
    # ── 混合意图 ────────────────────────────────────────────
    {
        "name": "08_混合意图_咨询加导航",
        "category": "混合意图",
        "query": "我的电脑触摸板失灵了，同时帮我找一下深圳南山区最近的联想维修中心，我想去现场处理",
    },
    # ── 闲聊 ────────────────────────────────────────────────
    {
        "name": "09_闲聊_系统介绍",
        "category": "闲聊",
        "query": "你好，你是什么系统？能帮我做什么？",
    },
]

# 多轮对话用例
MULTI_TURN_CASE = {
    "name": "10_多轮对话_上下文追问",
    "category": "多轮对话",
    "turns": [
        {"turn": 1, "query": "我的联想笔记本开机很慢，需要等3分钟才能进桌面"},
        {"turn": 2, "query": "你说的那个方法我试过了，没有明显改善，还有别的办法吗？"},
    ],
}


# ─────────────────────────────────────────────────────────────
# 结果数据结构
# ─────────────────────────────────────────────────────────────
@dataclass
class CaseResult:
    name: str
    category: str
    query: str
    # 耗时（秒）
    ttft: Optional[float] = None        # 首字时间（Time To First Token）
    total_time: Optional[float] = None  # 总耗时
    # 内容统计
    thinking_chars: int = 0             # THINKING 类型字符数
    processing_events: int = 0         # PROCESSING 类型事件数（工具调用提示）
    answer_chars: int = 0               # ANSWER 类型字符数
    answer_text: str = ""               # 完整回答文本（截断显示）
    # 状态
    finished_reason: Optional[str] = None
    error: Optional[str] = None
    success: bool = False


# ─────────────────────────────────────────────────────────────
# SSE 请求核心逻辑
# ─────────────────────────────────────────────────────────────
async def call_sse(client: httpx.AsyncClient, query: str, name: str, category: str) -> CaseResult:
    """发起单条 SSE 请求并收集指标"""
    result = CaseResult(name=name, category=category, query=query)
    payload = {
        "query": query,
        "user_context": {
            "user_id": USER_ID,
            "session_id": SESSION_ID,
        },
    }

    t_start = time.perf_counter()
    first_token_received = False
    answer_parts: list[str] = []

    try:
        async with client.stream(
            "POST",
            BASE_URL,
            json=payload,
            timeout=TIMEOUT,
            headers={"Accept": "text/event-stream"},
        ) as resp:
            resp.raise_for_status()
            buffer = ""
            async for raw_chunk in resp.aiter_text():
                buffer += raw_chunk
                # SSE 以空行分隔事件
                while "\n\n" in buffer:
                    event_block, buffer = buffer.split("\n\n", 1)
                    for line in event_block.splitlines():
                        if not line.startswith("data:"):
                            continue
                        json_str = line[len("data:"):].strip()
                        if not json_str:
                            continue
                        try:
                            msg = json.loads(json_str)
                        except json.JSONDecodeError:
                            continue

                        # 记录首字时间
                        if not first_token_received:
                            result.ttft = time.perf_counter() - t_start
                            first_token_received = True

                        status = msg.get("status", "")
                        data = msg.get("data", {})
                        msg_type = data.get("message_type", "")

                        if msg_type == "delta":
                            render_type = data.get("render_type", "")
                            text = data.get("data", "")
                            if render_type == "THINKING":
                                result.thinking_chars += len(text)
                            elif render_type == "PROCESSING":
                                result.processing_events += 1
                            elif render_type == "ANSWER":
                                result.answer_chars += len(text)
                                answer_parts.append(text)

                        elif msg_type == "finish" or status == "FINISHED":
                            metadata = msg.get("metadata", {})
                            result.finished_reason = metadata.get("finished_reason")
                            if metadata.get("error_message"):
                                result.error = metadata["error_message"]

        result.total_time = time.perf_counter() - t_start
        result.answer_text = "".join(answer_parts)
        result.success = True

    except Exception as e:
        result.total_time = time.perf_counter() - t_start
        result.error = str(e)
        result.success = False

    return result


# ─────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────
async def main():
    all_results: list[CaseResult] = []

    async with httpx.AsyncClient() as client:
        # ── 单轮测试 ─────────────────────────────────────────
        for case in SINGLE_TURN_CASES:
            print(f"\n{'─' * 60}")
            print(f"[{case['name']}]  {case['category']}")
            print(f"Query: {case['query']}")
            print("─" * 60)

            result = await call_sse(
                client=client,
                query=case["query"],
                name=case["name"],
                category=case["category"],
            )
            all_results.append(result)
            _print_case_inline(result)

        # ── 多轮对话 ─────────────────────────────────────────
        print(f"\n{'─' * 60}")
        print(f"[{MULTI_TURN_CASE['name']}]  {MULTI_TURN_CASE['category']}")
        print("─" * 60)
        for turn_info in MULTI_TURN_CASE["turns"]:
            turn_num = turn_info["turn"]
            query = turn_info["query"]
            turn_name = f"{MULTI_TURN_CASE['name']}_第{turn_num}轮"
            print(f"\n--- 第 {turn_num} 轮 ---")
            print(f"Query: {query}")

            result = await call_sse(
                client=client,
                query=query,
                name=turn_name,
                category=MULTI_TURN_CASE["category"],
            )
            # 多轮对话复用同一 session，标记轮次
            result.query = f"[第{turn_num}轮] {query}"
            all_results.append(result)
            _print_case_inline(result)

    # ── 汇总报告 ──────────────────────────────────────────────
    _print_summary(all_results)


def _print_case_inline(result: CaseResult):
    """单条用例结束后打印简要结果"""
    status = "✓" if result.success else "✗"
    ttft_str = f"{result.ttft:.2f}s" if result.ttft is not None else "N/A"
    total_str = f"{result.total_time:.2f}s" if result.total_time is not None else "N/A"
    print(f"{status} 首字: {ttft_str}  总耗时: {total_str}  "
          f"思考: {result.thinking_chars}字  工具调用: {result.processing_events}次  "
          f"回答: {result.answer_chars}字  完成原因: {result.finished_reason or '-'}")
    if result.error:
        print(f"  ERROR: {result.error}")
    # 打印回答摘要（最多 200 字）
    if result.answer_text:
        preview = result.answer_text[:200].replace("\n", " ")
        suffix = "..." if len(result.answer_text) > 200 else ""
        print(f"  回答预览: {preview}{suffix}")


def _print_summary(results: list[CaseResult]):
    """打印完整汇总报告"""
    print(f"\n{'=' * 80}")
    print("                          测试汇总报告")
    print(f"{'=' * 80}")
    print(f"{'用例名称':<35} {'类别':<10} {'状态':<4} {'首字':<8} {'总耗时':<9} "
          f"{'工具调用':<8} {'回答字数':<8} {'完成原因'}")
    print(f"{'─' * 80}")

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    for r in results:
        status = "✓" if r.success else "✗"
        ttft_str = f"{r.ttft:.2f}s" if r.ttft is not None else "N/A"
        total_str = f"{r.total_time:.2f}s" if r.total_time is not None else "N/A"
        reason = r.finished_reason or ("-" if r.success else "ERROR")
        print(f"{r.name:<35} {r.category:<10} {status:<4} {ttft_str:<8} {total_str:<9} "
              f"{r.processing_events:<8} {r.answer_chars:<8} {reason}")

    print(f"{'─' * 80}")

    # 统计汇总
    total_count = len(results)
    success_count = len(successful)
    print(f"\n总用例数: {total_count}  成功: {success_count}  失败: {len(failed)}")

    if successful:
        ttft_values = [r.ttft for r in successful if r.ttft is not None]
        total_values = [r.total_time for r in successful if r.total_time is not None]

        if ttft_values:
            avg_ttft = sum(ttft_values) / len(ttft_values)
            max_ttft = max(ttft_values)
            min_ttft = min(ttft_values)
            print(f"\n首字时间 (TTFT):")
            print(f"  平均: {avg_ttft:.2f}s  最快: {min_ttft:.2f}s  最慢: {max_ttft:.2f}s")

        if total_values:
            avg_total = sum(total_values) / len(total_values)
            max_total = max(total_values)
            min_total = min(total_values)
            print(f"\n总耗时:")
            print(f"  平均: {avg_total:.2f}s  最快: {min_total:.2f}s  最慢: {max_total:.2f}s")

        # 按类别分组统计
        categories: dict[str, list[CaseResult]] = {}
        for r in successful:
            categories.setdefault(r.category, []).append(r)

        print(f"\n按类别平均总耗时:")
        for cat, cat_results in categories.items():
            times = [r.total_time for r in cat_results if r.total_time is not None]
            if times:
                print(f"  {cat:<10}: {sum(times) / len(times):.2f}s  (样本数: {len(times)})")

    if failed:
        print(f"\n失败用例详情:")
        for r in failed:
            print(f"  [{r.name}] {r.error}")

    print(f"\n{'=' * 80}")


if __name__ == "__main__":
    asyncio.run(main())
