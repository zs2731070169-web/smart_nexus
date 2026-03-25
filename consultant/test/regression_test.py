"""
回归测试 - consultant 模块（全部5个接口）
测试范围：各接口的正常路径、异常路径、边界条件、鉴权校验
运行前提：服务已启动（http://127.0.0.1:8001）
运行方式：cd consultant && python test/regression_test.py
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
import requests
from datetime import datetime

BASE_URL = "http://127.0.0.1:8001/smart/nexus/consultant"
TIMEOUT = 30  # 秒

# 每次运行使用不同的手机号前缀，避免60s验证码冷却期冲突
_RUN_SUFFIX = random.randint(10000000, 19999999)

def _phone(index=0):
    """生成本次运行专属测试手机号（避免与上次运行冲突）"""
    base = (_RUN_SUFFIX + index) % 90000000 + 10000000
    return f"186{base}"


# =====================================================================
# 测试框架
# =====================================================================

class TestStats:
    def __init__(self):
        self.results = []
        self.start = time.time()

    def record(self, name, passed, msg="", elapsed=0.0):
        self.results.append({"name": name, "passed": passed, "msg": msg, "elapsed": elapsed})
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] ({elapsed*1000:.0f}ms) {name}" + (f"\n         ↳ {msg}" if (not passed and msg) else ""))

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        elapsed = time.time() - self.start
        pass_rate = (passed / total * 100) if total else 0
        all_times = [r["elapsed"] for r in self.results]
        avg_ms = (sum(all_times) / len(all_times) * 1000) if all_times else 0

        print("\n" + "=" * 65)
        print("  回归测试统计指标")
        print("=" * 65)
        print(f"  测试总数          : {total}")
        print(f"  通过 (PASS)       : {passed}  ✓")
        print(f"  失败 (FAIL)       : {failed}  ✗")
        print(f"  通过率            : {pass_rate:.1f}%")
        print(f"  总耗时            : {elapsed:.3f}s")
        print(f"  平均请求耗时      : {avg_ms:.0f}ms")
        if self.results:
            max_r = max(self.results, key=lambda r: r["elapsed"])
            min_r = min(self.results, key=lambda r: r["elapsed"])
            print(f"  最慢用例          : {max_r['name']} ({max_r['elapsed']*1000:.0f}ms)")
            print(f"  最快用例          : {min_r['name']} ({min_r['elapsed']*1000:.0f}ms)")
        print("=" * 65)

        if failed > 0:
            print("\n  失败用例明细：")
            for r in self.results:
                if not r["passed"]:
                    print(f"  [FAIL] {r['name']}")
                    if r["msg"]:
                        print(f"         {r['msg']}")
        return failed == 0


stats = TestStats()


def _req(method, path, **kwargs):
    """发送 HTTP 请求，返回 (response, elapsed_seconds)"""
    url = f"{BASE_URL}{path}"
    start = time.time()
    try:
        resp = requests.request(method, url, timeout=TIMEOUT, **kwargs)
        return resp, time.time() - start
    except requests.exceptions.ConnectionError as e:
        raise SystemExit(f"\n[FATAL] 无法连接到服务器 {url}\n原因：{e}\n请先启动 consultant 服务！")


def _get_code_and_login(phone):
    """辅助：获取验证码并登录，返回 auth_token"""
    r, _ = _req("POST", "/code", json={"user_phone": phone})
    body = r.json()
    if body.get("status") != "200":
        return None, body.get("message", "获取验证码失败")
    code = body["code"]
    r2, _ = _req("POST", "/login", json={"user_phone": phone, "code": code})
    body2 = r2.json()
    if body2.get("status") != "200":
        return None, body2.get("message", "登录失败")
    return body2["auth_token"], None


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# TC-CODE：获取登录验证码接口
# =====================================================================

def test_code_group():
    print("\n▶ /code — 获取登录验证码")

    # TC-CODE-01：有效手机号返回6位验证码
    phone = _phone(1)
    r, elapsed = _req("POST", "/code", json={"user_phone": phone})
    body = r.json()
    passed = (
        r.status_code == 200
        and body.get("status") == "200"
        and len(body.get("code", "")) == 6
        and body["code"].isdigit()
    )
    stats.record("TC-CODE-01 有效手机号返回6位数字验证码", passed,
                 f"status={body.get('status')} code={body.get('code')}", elapsed)

    # TC-CODE-02：重复获取同一手机号的验证码应被拒绝（60s内）
    r2, elapsed2 = _req("POST", "/code", json={"user_phone": phone})
    body2 = r2.json()
    passed2 = (r2.status_code == 200 and body2.get("status") == "500"
               and "重复" in body2.get("message", ""))
    stats.record("TC-CODE-02 60s内重复获取同号验证码应拒绝", passed2,
                 f"status={body2.get('status')} msg={body2.get('message','')[:60]}", elapsed2)

    # TC-CODE-03：无效手机号 — 短号码
    r3, elapsed3 = _req("POST", "/code", json={"user_phone": "1234567"})
    body3 = r3.json()
    passed3 = (r3.status_code == 200 and body3.get("status") == "500")
    stats.record("TC-CODE-03 短号码（7位）应返回业务错误", passed3,
                 f"msg={body3.get('message','')[:80]}", elapsed3)

    # TC-CODE-04：无效手机号 — 以12开头
    r4, elapsed4 = _req("POST", "/code", json={"user_phone": "12345678901"})
    body4 = r4.json()
    passed4 = (r4.status_code == 200 and body4.get("status") == "500")
    stats.record("TC-CODE-04 12开头号码应返回业务错误", passed4,
                 f"msg={body4.get('message','')[:80]}", elapsed4)

    # TC-CODE-05：手机号含字母
    r5, elapsed5 = _req("POST", "/code", json={"user_phone": "1861234567a"})
    body5 = r5.json()
    passed5 = (r5.status_code == 200 and body5.get("status") == "500")
    stats.record("TC-CODE-05 含字母手机号应返回业务错误", passed5,
                 f"msg={body5.get('message','')[:80]}", elapsed5)

    # TC-CODE-06：手机号为空字符串
    r6, elapsed6 = _req("POST", "/code", json={"user_phone": ""})
    body6 = r6.json()
    passed6 = (r6.status_code == 200 and body6.get("status") == "500")
    stats.record("TC-CODE-06 空手机号应返回业务错误", passed6,
                 f"msg={body6.get('message','')[:80]}", elapsed6)

    # TC-CODE-07：缺少 user_phone 字段（Pydantic 应返回 422）
    r7, elapsed7 = _req("POST", "/code", json={})
    passed7 = (r7.status_code == 422)
    stats.record("TC-CODE-07 缺少 user_phone 字段返回 422", passed7,
                 f"status_code={r7.status_code}", elapsed7)

    # TC-CODE-08：带 +86 前缀的有效手机号
    phone8 = _phone(8)
    r8, elapsed8 = _req("POST", "/code", json={"user_phone": f"+86{phone8}"})
    body8 = r8.json()
    passed8 = (r8.status_code == 200 and body8.get("status") == "200")
    stats.record("TC-CODE-08 +86前缀有效手机号应返回验证码", passed8,
                 f"status={body8.get('status')} msg={body8.get('message','')[:60]}", elapsed8)


# =====================================================================
# TC-LOGIN：用户登录接口
# =====================================================================

def test_login_group():
    print("\n▶ /login — 用户登录")

    # TC-LOGIN-01：正确验证码登录成功
    phone = _phone(20)
    r_code, _ = _req("POST", "/code", json={"user_phone": phone})
    code = r_code.json().get("code", "")
    r, elapsed = _req("POST", "/login", json={"user_phone": phone, "code": code})
    body = r.json()
    passed = (
        r.status_code == 200
        and body.get("status") == "200"
        and body.get("auth_token") is not None
        and len(body.get("auth_token", "")) > 20
    )
    stats.record("TC-LOGIN-01 正确验证码登录成功，返回 JWT", passed,
                 f"status={body.get('status')} msg={body.get('message','')[:80]} token_len={len(body.get('auth_token') or '')}", elapsed)

    # TC-LOGIN-02：登录成功后再次登录应被拒绝
    if code:
        # 第二次用相同 phone 重新获取验证码（前一个已消耗，这里模拟已登录）
        r2, elapsed2 = _req("POST", "/login", json={"user_phone": phone, "code": "000000"})
        body2 = r2.json()
        # 已登录用户应被拒绝
        passed2 = (r2.status_code == 200 and body2.get("status") == "500"
                   and ("已登录" in body2.get("message", "") or "重复" in body2.get("message", "")))
        stats.record("TC-LOGIN-02 已登录用户再次登录应被拒绝", passed2,
                     f"msg={body2.get('message','')[:80]}", elapsed2)

    # TC-LOGIN-03：错误验证码
    phone3 = _phone(30)
    _req("POST", "/code", json={"user_phone": phone3})  # 先获取验证码
    r3, elapsed3 = _req("POST", "/login", json={"user_phone": phone3, "code": "000000"})
    body3 = r3.json()
    passed3 = (r3.status_code == 200 and body3.get("status") == "500"
               and body3.get("auth_token") is None
               and "不正确" in body3.get("message", ""))
    stats.record("TC-LOGIN-03 错误验证码登录失败", passed3,
                 f"status={body3.get('status')} msg={body3.get('message','')[:80]}", elapsed3)

    # TC-LOGIN-04：验证码过期（使用从未获取过验证码的手机号）
    phone4 = _phone(40)
    r4, elapsed4 = _req("POST", "/login", json={"user_phone": phone4, "code": "123456"})
    body4 = r4.json()
    passed4 = (r4.status_code == 200 and body4.get("status") == "500"
               and ("过期" in body4.get("message", "") or "获取" in body4.get("message", "")))
    stats.record("TC-LOGIN-04 未获取验证码直接登录应失败", passed4,
                 f"msg={body4.get('message','')[:80]}", elapsed4)

    # TC-LOGIN-05：空验证码
    phone5 = _phone(50)
    _req("POST", "/code", json={"user_phone": phone5})
    r5, elapsed5 = _req("POST", "/login", json={"user_phone": phone5, "code": ""})
    body5 = r5.json()
    passed5 = (r5.status_code == 200 and body5.get("status") == "500"
               and "空" in body5.get("message", ""))
    stats.record("TC-LOGIN-05 空验证码登录失败", passed5,
                 f"msg={body5.get('message','')[:80]}", elapsed5)

    # TC-LOGIN-06：无效手机号格式
    r6, elapsed6 = _req("POST", "/login", json={"user_phone": "12345", "code": "123456"})
    body6 = r6.json()
    passed6 = (r6.status_code == 200 and body6.get("status") == "500")
    stats.record("TC-LOGIN-06 无效手机号格式登录失败", passed6,
                 f"msg={body6.get('message','')[:80]}", elapsed6)

    # TC-LOGIN-07：缺少字段（Pydantic 校验）
    r7, elapsed7 = _req("POST", "/login", json={"user_phone": "18612345678"})
    passed7 = (r7.status_code == 422)
    stats.record("TC-LOGIN-07 缺少 code 字段返回 422", passed7,
                 f"status_code={r7.status_code}", elapsed7)

    # TC-LOGIN-08：登录响应不含明文密码/验证码（安全校验）
    phone8 = _phone(80)
    r_c8, _ = _req("POST", "/code", json={"user_phone": phone8})
    code8 = r_c8.json().get("code", "")
    r8, elapsed8 = _req("POST", "/login", json={"user_phone": phone8, "code": code8})
    body8 = r8.json()
    resp_str = json.dumps(body8)
    passed8 = (body8.get("status") == "200" and code8 not in resp_str)
    stats.record("TC-LOGIN-08 登录响应不暴露明文验证码", passed8,
                 f"resp keys={list(body8.keys())}", elapsed8)


# =====================================================================
# TC-LOGOUT：退出登录接口
# =====================================================================

def test_logout_group():
    print("\n▶ /logout — 退出登录")

    # 先登录获取有效 token
    phone = _phone(100)
    token, err = _get_code_and_login(phone)

    # TC-LOGOUT-01：有效 token 退出成功
    if token:
        r, elapsed = _req("DELETE", "/logout", headers=_auth_headers(token))
        body = r.json()
        passed = (r.status_code == 200 and body.get("status") == "200")
        stats.record("TC-LOGOUT-01 有效 token 退出成功", passed,
                     f"status={body.get('status')} msg={body.get('message','')}", elapsed)
    else:
        stats.record("TC-LOGOUT-01 有效 token 退出成功", False, f"前置登录失败: {err}", 0)

    # TC-LOGOUT-02：已退出的 token 再次退出（应鉴权失败或业务失败）
    if token:
        r2, elapsed2 = _req("DELETE", "/logout", headers=_auth_headers(token))
        body2 = r2.json()
        # 退出后 token 失效，应返回 401 或业务 500
        status_val2 = body2.get("status", "") if isinstance(body2, dict) else ""
        passed2 = (r2.status_code == 401 or status_val2 == "500")
        stats.record("TC-LOGOUT-02 已退出 token 再次退出应失败", passed2,
                     f"http={r2.status_code} status={status_val2}", elapsed2)
    else:
        stats.record("TC-LOGOUT-02 已退出 token 再次退出应失败", False, "前置登录失败", 0)

    # TC-LOGOUT-03：无 Authorization 头
    r3, elapsed3 = _req("DELETE", "/logout")
    passed3 = (r3.status_code == 401)
    stats.record("TC-LOGOUT-03 无 Authorization 头返回 401", passed3,
                 f"http={r3.status_code}", elapsed3)

    # TC-LOGOUT-04：伪造 Bearer token
    r4, elapsed4 = _req("DELETE", "/logout",
                        headers={"Authorization": "Bearer fake.token.value"})
    passed4 = (r4.status_code == 401)
    stats.record("TC-LOGOUT-04 伪造 Bearer token 返回 401", passed4,
                 f"http={r4.status_code}", elapsed4)

    # TC-LOGOUT-05：Authorization 格式错误（不含 Bearer）
    r5, elapsed5 = _req("DELETE", "/logout",
                        headers={"Authorization": "InvalidTokenWithoutBearer"})
    passed5 = (r5.status_code == 401)
    stats.record("TC-LOGOUT-05 Authorization 格式错误返回 401", passed5,
                 f"http={r5.status_code}", elapsed5)

    # TC-LOGOUT-06：空 token
    r6, elapsed6 = _req("DELETE", "/logout",
                        headers={"Authorization": "Bearer "})
    passed6 = (r6.status_code == 401)
    stats.record("TC-LOGOUT-06 空 Bearer token 返回 401", passed6,
                 f"http={r6.status_code}", elapsed6)


# =====================================================================
# TC-CHAT：流式对话接口
# =====================================================================

def _parse_sse(response) -> list:
    """解析 SSE 响应，返回所有事件数据列表"""
    events = []
    for line in response.iter_lines():
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        if line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            if data_str:
                try:
                    events.append(json.loads(data_str))
                except json.JSONDecodeError:
                    pass
    return events


def test_chat_group():
    print("\n▶ /chat — 流式对话接口")

    # 先登录
    phone = _phone(200)
    token, err = _get_code_and_login(phone)

    # TC-CHAT-01：有效请求，SSE 响应格式正确
    if token:
        session_id = str(uuid.uuid4())
        r, elapsed = _req(
            "POST", "/chat",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            json={"query": "你好，请介绍一下你自己", "session_id": session_id},
            stream=True,
        )
        events = _parse_sse(r)
        has_delta = any(e.get("data", {}).get("message_type") == "delta" for e in events)
        has_finish = any(e.get("data", {}).get("message_type") == "finish" for e in events)
        finish_events = [e for e in events if e.get("data", {}).get("message_type") == "finish"]
        normal_finish = (
            finish_events
            and finish_events[-1].get("metadata", {}).get("finished_reason") == "NORMAL"
        )
        passed = (
            r.status_code == 200
            and has_delta
            and has_finish
            and normal_finish
            and len(events) > 1
        )
        stats.record(
            f"TC-CHAT-01 有效请求 SSE 格式正确（{len(events)} 条事件）", passed,
            f"delta={has_delta} finish={has_finish} normal={normal_finish}", elapsed,
        )
    else:
        stats.record("TC-CHAT-01 有效请求 SSE 格式正确", False, f"前置登录失败: {err}", 0)

    # TC-CHAT-02：SSE 中包含 ANSWER 类型消息
    if token:
        r2, elapsed2 = _req(
            "POST", "/chat",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            json={"query": "联想笔记本保修期是多久", "session_id": str(uuid.uuid4())},
            stream=True,
        )
        events2 = _parse_sse(r2)
        answer_events = [
            e for e in events2
            if e.get("data", {}).get("render_type") == "ANSWER"
        ]
        passed2 = len(answer_events) > 0
        stats.record("TC-CHAT-02 响应中包含 ANSWER 类型消息", passed2,
                     f"ANSWER事件数={len(answer_events)}", elapsed2)
    else:
        stats.record("TC-CHAT-02 响应中包含 ANSWER 类型消息", False, "前置登录失败", 0)

    # TC-CHAT-03：缺少 session_id，应异常结束
    if token:
        r3, elapsed3 = _req(
            "POST", "/chat",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            json={"query": "测试", "session_id": ""},
            stream=True,
        )
        events3 = _parse_sse(r3)
        exception_finish = any(
            e.get("metadata", {}).get("finished_reason") == "EXCEPTION"
            for e in events3
        )
        passed3 = r3.status_code == 200 and exception_finish
        stats.record("TC-CHAT-03 空 session_id 应异常结束", passed3,
                     f"events={len(events3)} exception={exception_finish}", elapsed3)
    else:
        stats.record("TC-CHAT-03 空 session_id 应异常结束", False, "前置登录失败", 0)

    # TC-CHAT-04：无 Authorization 头
    r4, elapsed4 = _req(
        "POST", "/chat",
        json={"query": "测试", "session_id": str(uuid.uuid4())},
    )
    passed4 = (r4.status_code == 401)
    stats.record("TC-CHAT-04 无 Authorization 头返回 401", passed4,
                 f"http={r4.status_code}", elapsed4)

    # TC-CHAT-05：伪造 token
    r5, elapsed5 = _req(
        "POST", "/chat",
        headers={"Authorization": "Bearer invalid.jwt.token"},
        json={"query": "测试", "session_id": str(uuid.uuid4())},
    )
    passed5 = (r5.status_code == 401)
    stats.record("TC-CHAT-05 伪造 token 返回 401", passed5,
                 f"http={r5.status_code}", elapsed5)

    # TC-CHAT-06：缺少 query 字段（422 参数校验）
    if token:
        r6, elapsed6 = _req(
            "POST", "/chat",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            json={"session_id": str(uuid.uuid4())},
        )
        passed6 = (r6.status_code == 422)
        stats.record("TC-CHAT-06 缺少 query 字段返回 422", passed6,
                     f"http={r6.status_code}", elapsed6)
    else:
        stats.record("TC-CHAT-06 缺少 query 字段返回 422", False, "前置登录失败", 0)

    # TC-CHAT-07：所有 SSE 事件 id 唯一
    if token:
        r7, elapsed7 = _req(
            "POST", "/chat",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            json={"query": "什么是ThinkPad", "session_id": str(uuid.uuid4())},
            stream=True,
        )
        events7 = _parse_sse(r7)
        ids = [e.get("id") for e in events7 if e.get("id")]
        passed7 = len(ids) == len(set(ids)) and len(ids) > 0
        stats.record("TC-CHAT-07 所有 SSE 事件 ID 唯一不重复", passed7,
                     f"events={len(events7)} ids={len(ids)} unique_ids={len(set(ids))}", elapsed7)
    else:
        stats.record("TC-CHAT-07 所有 SSE 事件 ID 唯一不重复", False, "前置登录失败", 0)

    # TC-CHAT-08：每条 SSE 事件含 metadata.create_time
    if token:
        r8, elapsed8 = _req(
            "POST", "/chat",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            json={"query": "你好", "session_id": str(uuid.uuid4())},
            stream=True,
        )
        events8 = _parse_sse(r8)
        all_have_time = all(e.get("metadata", {}).get("create_time") for e in events8)
        passed8 = all_have_time and len(events8) > 0
        stats.record("TC-CHAT-08 所有 SSE 事件包含 create_time", passed8,
                     f"events={len(events8)} all_have_time={all_have_time}", elapsed8)
    else:
        stats.record("TC-CHAT-08 所有 SSE 事件包含 create_time", False, "前置登录失败", 0)

    # 退出本组登录
    if token:
        _req("DELETE", "/logout", headers=_auth_headers(token))


# =====================================================================
# TC-HISTORY：查询历史会话接口
# =====================================================================

def test_history_group():
    print("\n▶ /query_chat_history — 查询对话历史")

    # 先登录并对话（确保有历史记录）
    phone = _phone(300)
    token, err = _get_code_and_login(phone)

    if token:
        # 发起一次对话，产生历史记录
        session_id = str(uuid.uuid4())
        r_chat, _ = _req(
            "POST", "/chat",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            json={"query": "联想电脑怎么激活Windows？", "session_id": session_id},
            stream=True,
        )
        list(r_chat.iter_lines())  # 消费全部 SSE 流，等待对话完成

    # TC-HISTORY-01：有效 token 查询，返回 chat_history_list
    if token:
        r, elapsed = _req("POST", "/query_chat_history", headers=_auth_headers(token))
        body = r.json()
        passed = (
            r.status_code == 200
            and body.get("status") == "200"
            and isinstance(body.get("chat_history_list"), list)
        )
        stats.record("TC-HISTORY-01 有效 token 查询返回历史列表", passed,
                     f"status={body.get('status')} count={len(body.get('chat_history_list',[]))}", elapsed)
    else:
        stats.record("TC-HISTORY-01 有效 token 查询返回历史列表", False, f"前置登录失败: {err}", 0)

    # TC-HISTORY-02：历史列表结构校验（有记录时）
    if token:
        r2, elapsed2 = _req("POST", "/query_chat_history", headers=_auth_headers(token))
        body2 = r2.json()
        hist_list = body2.get("chat_history_list", [])
        if hist_list:
            first = hist_list[0]
            passed2 = (
                "session_id" in first
                and "file_time" in first
                and isinstance(first.get("history_list"), list)
            )
            stats.record("TC-HISTORY-02 历史条目结构包含 session_id/file_time/history_list", passed2,
                         f"keys={list(first.keys())}", elapsed2)
        else:
            stats.record("TC-HISTORY-02 历史条目结构包含 session_id/file_time/history_list",
                         True, "暂无历史记录，结构校验跳过", elapsed2)
    else:
        stats.record("TC-HISTORY-02 历史条目结构校验", False, "前置登录失败", 0)

    # TC-HISTORY-03：历史中不含 role=system 消息
    if token:
        r3, elapsed3 = _req("POST", "/query_chat_history", headers=_auth_headers(token))
        body3 = r3.json()
        hist_list3 = body3.get("chat_history_list", [])
        all_no_system = all(
            m.get("role") != "system"
            for session in hist_list3
            for m in session.get("history_list", [])
        )
        passed3 = all_no_system
        stats.record("TC-HISTORY-03 历史列表不含 role=system 消息", passed3,
                     f"sessions={len(hist_list3)}", elapsed3)
    else:
        stats.record("TC-HISTORY-03 历史列表不含 role=system 消息", False, "前置登录失败", 0)

    # TC-HISTORY-04：无 Authorization 头
    r4, elapsed4 = _req("POST", "/query_chat_history")
    passed4 = (r4.status_code == 401)
    stats.record("TC-HISTORY-04 无 Authorization 头返回 401", passed4,
                 f"http={r4.status_code}", elapsed4)

    # TC-HISTORY-05：伪造 token
    r5, elapsed5 = _req("POST", "/query_chat_history",
                        headers={"Authorization": "Bearer fake.invalid.token"})
    passed5 = (r5.status_code == 401)
    stats.record("TC-HISTORY-05 伪造 token 返回 401", passed5,
                 f"http={r5.status_code}", elapsed5)

    # TC-HISTORY-06：退出后使用旧 token 查询应失败
    if token:
        _req("DELETE", "/logout", headers=_auth_headers(token))
        r6, elapsed6 = _req("POST", "/query_chat_history", headers=_auth_headers(token))
        passed6 = (r6.status_code == 401 or r6.json().get("status") == "500")
        stats.record("TC-HISTORY-06 退出后旧 token 查询历史应失败", passed6,
                     f"http={r6.status_code}", elapsed6)
    else:
        stats.record("TC-HISTORY-06 退出后旧 token 查询历史应失败", False, "前置登录失败", 0)


# =====================================================================
# 主入口
# =====================================================================

def main():
    print("\n" + "=" * 65)
    print("  回归测试 — consultant 模块（全部5个接口）")
    print(f"  服务地址：{BASE_URL}")
    print(f"  运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    # 检查服务可达性
    try:
        requests.get(BASE_URL.rsplit("/consultant", 1)[0] + "/docs", timeout=5)
    except requests.exceptions.ConnectionError:
        pass  # 不一定有 /docs，忽略

    test_code_group()
    test_login_group()
    test_logout_group()
    test_chat_group()
    test_history_group()

    return stats.summary()


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
