"""
性能测试 - consultant 模块
测试范围：响应时间、并发吞吐量、错误率、百分位延迟
说明：
  - /code /login /logout /query_chat_history 为快速接口，重点测并发和延迟
  - /chat 为 LLM 流式接口，重点测首字节延迟（TTFB）和流式完成时间
  - 性能测试不调整并发量过大，以免影响服务稳定性
运行前提：服务已启动（http://127.0.0.1:8001）
运行方式：cd consultant && python test/performance_test.py
"""
import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
import time
import uuid
import random
import statistics
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

BASE_URL = "http://127.0.0.1:8001/smart/nexus/consultant"
TIMEOUT = 60

_RUN_SUFFIX = random.randint(30000000, 39999999)
_phone_counter = 0
_phone_lock = threading.Lock()


def _next_phone():
    global _phone_counter
    with _phone_lock:
        _phone_counter += 1
        base = (_RUN_SUFFIX + _phone_counter) % 90000000 + 10000000
        return f"186{base}"


def _req(method, path, **kwargs):
    url = f"{BASE_URL}{path}"
    try:
        return requests.request(method, url, timeout=TIMEOUT, **kwargs)
    except requests.exceptions.ConnectionError as e:
        raise SystemExit(f"\n[FATAL] 无法连接服务 {url}: {e}\n请先启动 consultant 服务！")
    except requests.exceptions.Timeout:
        return None


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _get_token(phone=None):
    """获取 auth_token（验证码+登录）"""
    if not phone:
        phone = _next_phone()
    r_code = _req("POST", "/code", json={"user_phone": phone})
    if not r_code or r_code.status_code != 200:
        return None, phone
    code = r_code.json().get("code")
    if not code:
        return None, phone
    r_login = _req("POST", "/login", json={"user_phone": phone, "code": code})
    if not r_login or r_login.status_code != 200:
        return None, phone
    token = r_login.json().get("auth_token")
    return token, phone


def _parse_sse_stream(response):
    """逐行解析 SSE，返回 (events, ttfb_seconds, total_seconds)"""
    ttfb = None
    start = time.time()
    events = []
    for line in response.iter_lines():
        if ttfb is None:
            ttfb = time.time() - start
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        if line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            if data_str:
                try:
                    events.append(json.loads(data_str))
                except json.JSONDecodeError:
                    pass
    total = time.time() - start
    return events, ttfb or total, total


# =====================================================================
# 指标计算工具
# =====================================================================

def _percentile(data, pct):
    if not data:
        return 0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * pct / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


def _print_latency_stats(label, times_ms, errors=0, total=None):
    if total is None:
        total = len(times_ms) + errors
    success = len(times_ms)
    error_rate = (errors / total * 100) if total else 0

    print(f"\n  📊 {label}")
    print(f"  {'─' * 50}")
    if times_ms:
        print(f"  请求总数          : {total}")
        print(f"  成功              : {success}")
        print(f"  失败/超时         : {errors}  (错误率 {error_rate:.1f}%)")
        print(f"  最小延迟          : {min(times_ms):.0f} ms")
        print(f"  最大延迟          : {max(times_ms):.0f} ms")
        print(f"  平均延迟          : {statistics.mean(times_ms):.0f} ms")
        if len(times_ms) > 1:
            print(f"  中位数 (P50)      : {_percentile(times_ms, 50):.0f} ms")
            print(f"  P75               : {_percentile(times_ms, 75):.0f} ms")
            print(f"  P95               : {_percentile(times_ms, 95):.0f} ms")
            print(f"  P99               : {_percentile(times_ms, 99):.0f} ms")
    else:
        print(f"  无有效请求数据（全部失败/超时）")


def _print_throughput_stats(label, elapsed_s, success_count, errors=0):
    total = success_count + errors
    tps = success_count / elapsed_s if elapsed_s > 0 else 0
    error_rate = (errors / total * 100) if total else 0
    print(f"\n  📊 {label}")
    print(f"  {'─' * 50}")
    print(f"  并发请求总数      : {total}")
    print(f"  成功              : {success_count}")
    print(f"  失败              : {errors}  (错误率 {error_rate:.1f}%)")
    print(f"  总耗时            : {elapsed_s:.2f}s")
    print(f"  吞吐量 (TPS)      : {tps:.2f} req/s")


# =====================================================================
# 全局统计汇总
# =====================================================================

class PerfSummary:
    def __init__(self):
        self.sections = []

    def add(self, label, passed, detail=""):
        self.sections.append({"label": label, "passed": passed, "detail": detail})

    def print_summary(self):
        print("\n" + "=" * 65)
        print("  性能测试汇总")
        print("=" * 65)
        for s in self.sections:
            icon = "✓" if s["passed"] else "⚠"
            print(f"  {icon} {s['label']}" + (f"  [{s['detail']}]" if s["detail"] else ""))
        print("=" * 65)


perf_summary = PerfSummary()


# =====================================================================
# PT-01：/code 串行响应时间基准
# =====================================================================

def test_code_serial_latency(n=10):
    print(f"\n{'=' * 65}")
    print(f"  PT-01: /code 串行响应时间基准（{n} 次）")
    print(f"{'=' * 65}")

    times_ms = []
    errors = 0
    for i in range(n):
        phone = _next_phone()
        start = time.time()
        r = _req("POST", "/code", json={"user_phone": phone})
        elapsed_ms = (time.time() - start) * 1000
        if r and r.status_code == 200 and r.json().get("status") == "200":
            times_ms.append(elapsed_ms)
        else:
            errors += 1
            print(f"  [WARN] 第{i+1}次失败: http={getattr(r, 'status_code', 'N/A')}")

    _print_latency_stats("/code 串行响应延迟", times_ms, errors)

    avg = statistics.mean(times_ms) if times_ms else 9999
    passed = avg < 2000  # 期望平均响应时间 < 2s
    perf_summary.add("PT-01 /code 平均延迟 < 2000ms", passed, f"avg={avg:.0f}ms")
    return times_ms


# =====================================================================
# PT-02：/login 串行响应时间基准
# =====================================================================

def test_login_serial_latency(n=10):
    print(f"\n{'=' * 65}")
    print(f"  PT-02: /login 串行响应时间基准（{n} 次）")
    print(f"{'=' * 65}")

    times_ms = []
    errors = 0
    for i in range(n):
        phone = _next_phone()
        r_code = _req("POST", "/code", json={"user_phone": phone})
        if not r_code or r_code.status_code != 200:
            errors += 1
            continue
        code = r_code.json().get("code")
        start = time.time()
        r_login = _req("POST", "/login", json={"user_phone": phone, "code": code})
        elapsed_ms = (time.time() - start) * 1000
        if r_login and r_login.status_code == 200 and r_login.json().get("status") == "200":
            times_ms.append(elapsed_ms)
            # 及时退出，释放数据库记录
            token = r_login.json().get("auth_token")
            if token:
                _req("DELETE", "/logout", headers=_auth(token))
        else:
            errors += 1

    _print_latency_stats("/login 串行响应延迟", times_ms, errors)

    avg = statistics.mean(times_ms) if times_ms else 9999
    passed = avg < 3000
    perf_summary.add("PT-02 /login 平均延迟 < 3000ms", passed, f"avg={avg:.0f}ms")
    return times_ms


# =====================================================================
# PT-03：/code 并发压测
# =====================================================================

def test_code_concurrent(concurrency=10):
    print(f"\n{'=' * 65}")
    print(f"  PT-03: /code 并发压测（{concurrency} 并发）")
    print(f"{'=' * 65}")

    phones = [_next_phone() for _ in range(concurrency)]
    times_ms = []
    errors = 0

    def call_code(phone):
        start = time.time()
        r = _req("POST", "/code", json={"user_phone": phone})
        elapsed_ms = (time.time() - start) * 1000
        if r and r.status_code == 200 and r.json().get("status") == "200":
            return elapsed_ms, None
        return None, f"status={getattr(r, 'status_code', 'timeout')} body={r.text[:50] if r else ''}"

    start_all = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(call_code, p) for p in phones]
        for future in as_completed(futures):
            elapsed, err = future.result()
            if elapsed is not None:
                times_ms.append(elapsed)
            else:
                errors += 1

    elapsed_all = time.time() - start_all
    _print_latency_stats(f"/code 并发延迟（{concurrency}并发）", times_ms, errors)
    _print_throughput_stats(f"/code 并发吞吐量", elapsed_all, len(times_ms), errors)

    error_rate = (errors / concurrency * 100) if concurrency else 0
    passed = error_rate < 20  # 期望错误率 < 20%
    perf_summary.add(f"PT-03 /code {concurrency}并发错误率 < 20%",
                     passed, f"error_rate={error_rate:.1f}%")
    return times_ms


# =====================================================================
# PT-04：/query_chat_history 并发压测
# =====================================================================

def test_history_concurrent(concurrency=8):
    print(f"\n{'=' * 65}")
    print(f"  PT-04: /query_chat_history 并发压测（{concurrency} 并发，复用同一 token）")
    print(f"{'=' * 65}")

    # 登录一次获取 token，用于并发测试
    token, phone = _get_token()
    if not token:
        print("  [WARN] 无法获取 token，跳过本测试")
        perf_summary.add("PT-04 /query_chat_history 并发", False, "无法登录")
        return []

    times_ms = []
    errors = 0

    def call_history():
        start = time.time()
        r = _req("POST", "/query_chat_history", headers=_auth(token))
        elapsed_ms = (time.time() - start) * 1000
        if r and r.status_code == 200 and r.json().get("status") == "200":
            return elapsed_ms, None
        return None, f"http={getattr(r, 'status_code', 'timeout')}"

    start_all = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(call_history) for _ in range(concurrency)]
        for future in as_completed(futures):
            elapsed, err = future.result()
            if elapsed is not None:
                times_ms.append(elapsed)
            else:
                errors += 1

    elapsed_all = time.time() - start_all
    _print_latency_stats(f"/query_chat_history 并发延迟（{concurrency}并发）", times_ms, errors)
    _print_throughput_stats(f"/query_chat_history 吞吐量", elapsed_all, len(times_ms), errors)

    _req("DELETE", "/logout", headers=_auth(token))

    avg = statistics.mean(times_ms) if times_ms else 9999
    passed = avg < 1000 and errors == 0
    perf_summary.add(f"PT-04 /query_chat_history {concurrency}并发平均 < 1000ms 且0错误",
                     passed, f"avg={avg:.0f}ms errors={errors}")
    return times_ms


# =====================================================================
# PT-05：/logout 并发压测
# =====================================================================

def test_logout_concurrent(concurrency=8):
    print(f"\n{'=' * 65}")
    print(f"  PT-05: /logout 并发压测（{concurrency} 用户并发退出）")
    print(f"{'=' * 65}")

    # 提前获取若干 token
    print(f"  准备 {concurrency} 个登录 token...")
    tokens = []
    for i in range(concurrency):
        token, _ = _get_token()
        if token:
            tokens.append(token)
    print(f"  成功获取 {len(tokens)}/{concurrency} 个 token")

    if not tokens:
        print("  [WARN] 无有效 token，跳过本测试")
        perf_summary.add("PT-05 /logout 并发", False, "无 token")
        return []

    times_ms = []
    errors = 0

    def call_logout(tok):
        start = time.time()
        r = _req("DELETE", "/logout", headers=_auth(tok))
        elapsed_ms = (time.time() - start) * 1000
        if r and r.status_code == 200 and r.json().get("status") == "200":
            return elapsed_ms, None
        return None, f"http={getattr(r, 'status_code', 'timeout')}"

    start_all = time.time()
    with ThreadPoolExecutor(max_workers=len(tokens)) as executor:
        futures = [executor.submit(call_logout, t) for t in tokens]
        for future in as_completed(futures):
            elapsed, err = future.result()
            if elapsed is not None:
                times_ms.append(elapsed)
            else:
                errors += 1

    elapsed_all = time.time() - start_all
    _print_latency_stats(f"/logout 并发延迟（{len(tokens)}并发）", times_ms, errors)
    _print_throughput_stats("/logout 吞吐量", elapsed_all, len(times_ms), errors)

    avg = statistics.mean(times_ms) if times_ms else 9999
    passed = avg < 1000 and errors == 0
    perf_summary.add(f"PT-05 /logout {len(tokens)}并发平均 < 1000ms 且0错误",
                     passed, f"avg={avg:.0f}ms errors={errors}")
    return times_ms


# =====================================================================
# PT-06：/chat 首字节延迟（TTFB）测试
# =====================================================================

def test_chat_ttfb(n=3):
    print(f"\n{'=' * 65}")
    print(f"  PT-06: /chat 首字节延迟（TTFB）测试（{n} 次）")
    print(f"  说明：TTFB = 从发送请求到收到第一个 SSE 事件的时间")
    print(f"{'=' * 65}")

    token, phone = _get_token()
    if not token:
        print("  [WARN] 无法获取 token，跳过")
        perf_summary.add("PT-06 /chat TTFB", False, "无法登录")
        return

    ttfb_list = []
    total_list = []
    event_counts = []
    errors = 0

    queries = [
        "联想笔记本电池如何保养？",
        "ThinkPad T系列有哪些型号？",
        "电脑运行缓慢如何排查？",
    ]

    for i in range(n):
        query = queries[i % len(queries)]
        session_id = str(uuid.uuid4())
        print(f"\n  Round {i+1}: '{query[:20]}...'")
        try:
            req_start = time.time()
            r = _req(
                "POST", "/chat",
                headers={**_auth(token), "Content-Type": "application/json"},
                json={"query": query, "session_id": session_id},
                stream=True,
            )
            if r is None:
                errors += 1
                print("  [WARN] 请求超时")
                continue

            events, ttfb, total = _parse_sse_stream(r)

            ttfb_ms = ttfb * 1000
            total_ms = total * 1000
            event_counts.append(len(events))

            normal_end = any(
                e.get("metadata", {}).get("finished_reason") == "NORMAL" for e in events
            )
            if normal_end:
                ttfb_list.append(ttfb_ms)
                total_list.append(total_ms)
                print(f"  TTFB={ttfb_ms:.0f}ms  完成时间={total_ms:.0f}ms  事件数={len(events)}")
            else:
                errors += 1
                finished_reason = next(
                    (e.get("metadata", {}).get("finished_reason") for e in events
                     if e.get("data", {}).get("message_type") == "finish"),
                    "unknown"
                )
                print(f"  [WARN] 未正常结束: finished_reason={finished_reason}")

        except Exception as e:
            errors += 1
            print(f"  [ERROR] {e}")

    if ttfb_list:
        print(f"\n  📊 /chat TTFB (首字节延迟)")
        print(f"  {'─' * 50}")
        print(f"  请求总数          : {n}")
        print(f"  成功              : {len(ttfb_list)}")
        print(f"  失败              : {errors}")
        print(f"  最小 TTFB         : {min(ttfb_list):.0f} ms")
        print(f"  最大 TTFB         : {max(ttfb_list):.0f} ms")
        print(f"  平均 TTFB         : {statistics.mean(ttfb_list):.0f} ms")
        if len(ttfb_list) > 1:
            print(f"  TTFB P50          : {_percentile(ttfb_list, 50):.0f} ms")

        print(f"\n  📊 /chat 完整响应时间（流式全部完成）")
        print(f"  {'─' * 50}")
        print(f"  最小              : {min(total_list):.0f} ms")
        print(f"  最大              : {max(total_list):.0f} ms")
        print(f"  平均              : {statistics.mean(total_list):.0f} ms")
        if event_counts:
            print(f"  平均 SSE 事件数   : {statistics.mean(event_counts):.1f}")

    _req("DELETE", "/logout", headers=_auth(token))

    avg_ttfb = statistics.mean(ttfb_list) if ttfb_list else 9999
    passed = avg_ttfb < 30000  # LLM 接口 TTFB < 30s（已考虑网络+LLM处理时间）
    perf_summary.add("PT-06 /chat 平均 TTFB < 30s（含LLM处理）",
                     passed, f"avg_ttfb={avg_ttfb:.0f}ms")


# =====================================================================
# PT-07：全接口端到端延迟对比
# =====================================================================

def test_end_to_end_latency_comparison():
    print(f"\n{'=' * 65}")
    print(f"  PT-07: 全接口端到端延迟对比（各接口单次串行）")
    print(f"{'=' * 65}")

    results = {}

    # /code
    phone = _next_phone()
    start = time.time()
    r = _req("POST", "/code", json={"user_phone": phone})
    code_ms = (time.time() - start) * 1000
    code = r.json().get("code") if r else None
    results["/code"] = code_ms
    print(f"  /code              : {code_ms:.0f} ms")

    # /login
    if code:
        start = time.time()
        r = _req("POST", "/login", json={"user_phone": phone, "code": code})
        login_ms = (time.time() - start) * 1000
        token = r.json().get("auth_token") if r else None
        results["/login"] = login_ms
        print(f"  /login             : {login_ms:.0f} ms")
    else:
        token = None
        results["/login"] = None
        print(f"  /login             : N/A（无验证码）")

    # /query_chat_history
    if token:
        start = time.time()
        r = _req("POST", "/query_chat_history", headers=_auth(token))
        hist_ms = (time.time() - start) * 1000
        results["/query_chat_history"] = hist_ms
        print(f"  /query_chat_history: {hist_ms:.0f} ms")

    # /logout
    if token:
        start = time.time()
        r = _req("DELETE", "/logout", headers=_auth(token))
        logout_ms = (time.time() - start) * 1000
        results["/logout"] = logout_ms
        print(f"  /logout            : {logout_ms:.0f} ms")

    print(f"\n  接口延迟排名（不含 /chat）：")
    sorted_results = sorted(
        [(k, v) for k, v in results.items() if v is not None],
        key=lambda x: x[1]
    )
    for i, (endpoint, ms) in enumerate(sorted_results, 1):
        bar = "█" * int(ms / 50) + "░" * max(0, 20 - int(ms / 50))
        print(f"  {i}. {endpoint:<25} {ms:>6.0f}ms  {bar}")

    passed = all(v is not None and v < 5000 for v in results.values() if v is not None)
    perf_summary.add("PT-07 全接口单次延迟 < 5000ms",
                     passed,
                     f"max={max((v for v in results.values() if v), default=0):.0f}ms")


# =====================================================================
# 主入口
# =====================================================================

def main():
    print("\n" + "=" * 65)
    print("  性能测试 — consultant 模块")
    print(f"  服务地址：{BASE_URL}")
    print(f"  运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    print("\n  注意：性能测试结果受服务器负载、网络状况、LLM API 响应速度影响")
    print("  /chat 接口涉及真实 LLM 调用，响应时间较长属预期行为")

    global_start = time.time()

    test_code_serial_latency(n=10)
    test_login_serial_latency(n=8)
    test_code_concurrent(concurrency=10)
    test_history_concurrent(concurrency=8)
    test_logout_concurrent(concurrency=6)
    test_chat_ttfb(n=3)
    test_end_to_end_latency_comparison()

    total_elapsed = time.time() - global_start

    perf_summary.print_summary()
    print(f"\n  性能测试总耗时：{total_elapsed:.1f}s")
    print("=" * 65)

    # 所有性能指标均达标则返回 0
    all_passed = all(s["passed"] for s in perf_summary.sections)
    return all_passed


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
