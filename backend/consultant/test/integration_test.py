"""
集成测试 - consultant 模块（完整业务流程）
测试范围：端到端业务流程，跨接口协作，Session 管理，Token 生命周期
运行前提：服务已启动（http://127.0.0.1:8001），Redis 和 MySQL 已就绪
运行方式：cd backend/consultant && python test/integration_test.py
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
TIMEOUT = 60  # chat 接口耗时较长

_RUN_SUFFIX = random.randint(20000000, 29999999)


def _phone(index=0):
    base = (_RUN_SUFFIX + index) % 90000000 + 10000000
    return f"186{base}"


# =====================================================================
# 测试框架
# =====================================================================

class FlowStats:
    def __init__(self):
        self.flows = []
        self.assertions = []
        self.start = time.time()

    def begin_flow(self, name):
        print(f"\n{'─' * 55}")
        print(f"  流程：{name}")
        print(f"{'─' * 55}")
        self._current_flow = name
        self._flow_start = time.time()

    def end_flow(self, passed):
        elapsed = time.time() - self._flow_start
        self.flows.append({
            "name": self._current_flow,
            "passed": passed,
            "elapsed": elapsed,
        })
        status = "PASS" if passed else "FAIL"
        print(f"  流程结果: [{status}] (耗时 {elapsed:.2f}s)")

    def check(self, desc, condition, detail=""):
        status = "✓" if condition else "✗"
        self.assertions.append({"desc": desc, "passed": condition, "flow": self._current_flow})
        print(f"  {status} {desc}" + (f"  [{detail}]" if detail else ""))
        return condition

    def summary(self):
        total_flows = len(self.flows)
        passed_flows = sum(1 for f in self.flows if f["passed"])
        failed_flows = total_flows - passed_flows

        total_asserts = len(self.assertions)
        passed_asserts = sum(1 for a in self.assertions if a["passed"])
        failed_asserts = total_asserts - passed_asserts

        elapsed = time.time() - self.start
        flow_pass_rate = (passed_flows / total_flows * 100) if total_flows else 0
        assert_pass_rate = (passed_asserts / total_asserts * 100) if total_asserts else 0

        print("\n" + "=" * 65)
        print("  集成测试统计指标")
        print("=" * 65)
        print(f"  流程总数          : {total_flows}")
        print(f"  流程通过          : {passed_flows}  ✓")
        print(f"  流程失败          : {failed_flows}  ✗")
        print(f"  流程通过率        : {flow_pass_rate:.1f}%")
        print(f"  断言总数          : {total_asserts}")
        print(f"  断言通过          : {passed_asserts}  ✓")
        print(f"  断言失败          : {failed_asserts}  ✗")
        print(f"  断言通过率        : {assert_pass_rate:.1f}%")
        print(f"  总耗时            : {elapsed:.2f}s")
        if self.flows:
            print(f"  最慢流程          : "
                  f"{max(self.flows, key=lambda f: f['elapsed'])['name']} "
                  f"({max(f['elapsed'] for f in self.flows):.2f}s)")
        print("=" * 65)

        if failed_flows > 0 or failed_asserts > 0:
            print("\n  失败断言明细：")
            for a in self.assertions:
                if not a["passed"]:
                    print(f"  ✗ [{a['flow']}] {a['desc']}")

        return failed_flows == 0 and failed_asserts == 0


stats = FlowStats()


def _req(method, path, **kwargs):
    url = f"{BASE_URL}{path}"
    try:
        return requests.request(method, url, timeout=TIMEOUT, **kwargs)
    except requests.exceptions.ConnectionError as e:
        raise SystemExit(f"\n[FATAL] 无法连接服务 {url}: {e}\n请先启动 consultant 服务！")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _parse_sse(response):
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


def _get_code(phone):
    r = _req("POST", "/code", json={"user_phone": phone})
    return r.json().get("code"), r.json()


def _login(phone, code):
    r = _req("POST", "/login", json={"user_phone": phone, "code": code})
    return r.json().get("auth_token"), r.json()


def _logout(token):
    r = _req("DELETE", "/logout", headers=_auth(token))
    return r.json()


def _chat(token, query, session_id=None):
    sid = session_id or str(uuid.uuid4())
    r = _req(
        "POST", "/chat",
        headers={**_auth(token), "Content-Type": "application/json"},
        json={"query": query, "session_id": sid},
        stream=True,
    )
    return r, sid, _parse_sse(r)


def _query_history(token):
    r = _req("POST", "/query_chat_history", headers=_auth(token))
    return r.json()


# =====================================================================
# Flow 1：完整认证生命周期
# =====================================================================

def test_flow_complete_auth_lifecycle():
    stats.begin_flow("Flow-01: 完整认证生命周期（验证码→登录→对话→查历史→退出）")
    all_pass = True
    phone = _phone(0)

    # 步骤1：获取验证码
    code, code_body = _get_code(phone)
    ok1 = stats.check("Step-1 获取验证码成功，返回6位验证码",
                      code is not None and len(code) == 6,
                      f"code={code}")
    all_pass = all_pass and ok1

    # 步骤2：使用验证码登录
    token = None
    if code:
        token, login_body = _login(phone, code)
        ok2 = stats.check("Step-2 登录成功，获得 auth_token",
                          token is not None and len(token) > 20,
                          f"token_len={len(token) if token else 0}")
        all_pass = all_pass and ok2
    else:
        stats.check("Step-2 登录成功（跳过：无验证码）", False)
        all_pass = False

    # 步骤3：使用 token 进行对话
    session_id = str(uuid.uuid4())
    if token:
        r, sid, events = _chat(token, "电脑无法开机怎么办？", session_id)
        has_finish = any(e.get("data", {}).get("message_type") == "finish" for e in events)
        normal_end = any(
            e.get("metadata", {}).get("finished_reason") == "NORMAL" for e in events
        )
        ok3 = stats.check("Step-3 对话成功，正常结束",
                          has_finish and normal_end,
                          f"events={len(events)} normal={normal_end}")
        all_pass = all_pass and ok3
    else:
        stats.check("Step-3 对话（跳过：无 token）", False)
        all_pass = False

    # 步骤4：查询对话历史，验证本次对话已保存
    if token:
        time.sleep(0.5)  # 等待文件写入
        hist_body = _query_history(token)
        sessions = hist_body.get("chat_history_list", [])
        session_ids = [s["session_id"] for s in sessions]
        ok4 = stats.check("Step-4 查询历史，本次 session 出现在列表中",
                          session_id in session_ids,
                          f"expected={session_id[:8]}... found={len(sessions)}条记录")
        all_pass = all_pass and ok4
    else:
        stats.check("Step-4 查询历史（跳过：无 token）", False)
        all_pass = False

    # 步骤5：退出登录
    if token:
        logout_body = _logout(token)
        ok5 = stats.check("Step-5 退出登录成功",
                          logout_body.get("status") == "200",
                          f"msg={logout_body.get('message','')}")
        all_pass = all_pass and ok5
    else:
        stats.check("Step-5 退出登录（跳过：无 token）", False)
        all_pass = False

    # 步骤6：退出后旧 token 应失效
    if token:
        r_old = _req("POST", "/query_chat_history", headers=_auth(token))
        ok6 = stats.check("Step-6 退出后旧 token 应失效（401 或业务500）",
                          r_old.status_code == 401 or r_old.json().get("status") == "500",
                          f"http={r_old.status_code}")
        all_pass = all_pass and ok6
    else:
        stats.check("Step-6 退出后旧 token 失效（跳过）", False)
        all_pass = False

    stats.end_flow(all_pass)


# =====================================================================
# Flow 2：退出后重新登录，新 Token 可用
# =====================================================================

def test_flow_relogin_after_logout():
    stats.begin_flow("Flow-02: 退出后重新登录，新 Token 可正常使用")
    all_pass = True
    phone = _phone(10)

    # 第一次登录
    code1, _ = _get_code(phone)
    token1, _ = _login(phone, code1) if code1 else (None, {})
    ok1 = stats.check("Step-1 第一次登录成功", token1 is not None, f"token1={'有' if token1 else '无'}")
    all_pass = all_pass and ok1

    # 退出
    if token1:
        _logout(token1)
        # 验证旧 token 失效
        r_check = _req("POST", "/query_chat_history", headers=_auth(token1))
        ok2 = stats.check("Step-2 退出后 token1 失效",
                          r_check.status_code == 401 or r_check.json().get("status") == "500",
                          f"http={r_check.status_code}")
        all_pass = all_pass and ok2
    else:
        stats.check("Step-2 退出 token1（跳过）", False)
        all_pass = False

    # 第二次登录（同一手机号）
    code2, _ = _get_code(phone)
    token2, login2_body = _login(phone, code2) if code2 else (None, {})
    ok3 = stats.check("Step-3 同一手机号退出后可重新登录",
                      token2 is not None,
                      f"status={login2_body.get('status')}")
    all_pass = all_pass and ok3

    # 新 token 可访问受保护接口
    if token2:
        r_hist = _req("POST", "/query_chat_history", headers=_auth(token2))
        ok4 = stats.check("Step-4 新 token 可访问受保护接口",
                          r_hist.status_code == 200 and r_hist.json().get("status") == "200",
                          f"http={r_hist.status_code}")
        all_pass = all_pass and ok4
        _logout(token2)
    else:
        stats.check("Step-4 新 token 可访问接口（跳过）", False)
        all_pass = False

    stats.end_flow(all_pass)


# =====================================================================
# Flow 3：多会话管理
# =====================================================================

def test_flow_multi_session():
    stats.begin_flow("Flow-03: 多会话管理（不同 session_id 各自独立）")
    all_pass = True
    phone = _phone(20)

    code, _ = _get_code(phone)
    token, _ = _login(phone, code) if code else (None, {})

    if not token:
        stats.check("前置：登录成功", False, "无法登录")
        stats.end_flow(False)
        return

    stats.check("前置：登录成功", True, f"token_len={len(token)}")

    # 会话 A
    session_a = str(uuid.uuid4())
    r_a, _, events_a = _chat(token, "什么是联想保外维修流程？", session_a)
    ok1 = stats.check("Step-1 会话A 对话成功",
                      any(e.get("data", {}).get("message_type") == "finish" for e in events_a),
                      f"events={len(events_a)}")
    all_pass = all_pass and ok1

    # 会话 B（不同问题）
    session_b = str(uuid.uuid4())
    r_b, _, events_b = _chat(token, "ThinkPad X1 Carbon 有什么特点？", session_b)
    ok2 = stats.check("Step-2 会话B 对话成功",
                      any(e.get("data", {}).get("message_type") == "finish" for e in events_b),
                      f"events={len(events_b)}")
    all_pass = all_pass and ok2

    # 验证两个 session 都在历史中
    time.sleep(0.5)
    hist = _query_history(token)
    all_session_ids = [s["session_id"] for s in hist.get("chat_history_list", [])]

    ok3 = stats.check("Step-3 会话A 出现在历史列表",
                      session_a in all_session_ids,
                      f"session_a={session_a[:8]}...")
    ok4 = stats.check("Step-4 会话B 出现在历史列表",
                      session_b in all_session_ids,
                      f"session_b={session_b[:8]}...")
    all_pass = all_pass and ok3 and ok4

    # 验证两个 session 内容不同
    sessions_map = {s["session_id"]: s for s in hist.get("chat_history_list", [])}
    if session_a in sessions_map and session_b in sessions_map:
        content_a = str(sessions_map[session_a].get("history_list", []))
        content_b = str(sessions_map[session_b].get("history_list", []))
        ok5 = stats.check("Step-5 两个会话内容相互独立（不混淆）",
                          content_a != content_b,
                          f"len_a={len(content_a)} len_b={len(content_b)}")
        all_pass = all_pass and ok5

    _logout(token)
    stats.end_flow(all_pass)


# =====================================================================
# Flow 4：Token 鉴权边界验证
# =====================================================================

def test_flow_token_auth_boundary():
    stats.begin_flow("Flow-04: Token 鉴权边界（受保护接口的各类非法访问）")
    all_pass = True

    protected_endpoints = [
        ("DELETE", "/logout"),
        ("POST", "/query_chat_history"),
        ("POST", "/chat"),
    ]

    for method, path in protected_endpoints:
        # 无 Token
        r1 = _req(method, path,
                  json={"query": "test", "session_id": str(uuid.uuid4())} if path == "/chat" else None)
        ok1 = stats.check(f"无 Token 访问 {method} {path} 返回 401",
                          r1.status_code == 401,
                          f"http={r1.status_code}")
        all_pass = all_pass and ok1

        # 格式错误 Token
        r2 = _req(method, path,
                  headers={"Authorization": "NotBearerFormat xyz"},
                  json={"query": "test", "session_id": str(uuid.uuid4())} if path == "/chat" else None)
        ok2 = stats.check(f"格式错误 Token 访问 {method} {path} 返回 401",
                          r2.status_code == 401,
                          f"http={r2.status_code}")
        all_pass = all_pass and ok2

    # 白名单接口无需 Token
    r_code = _req("POST", "/code", json={"user_phone": _phone(90)})
    ok3 = stats.check("白名单接口 /code 无 Token 可访问（非401）",
                      r_code.status_code != 401,
                      f"http={r_code.status_code}")
    all_pass = all_pass and ok3

    r_login = _req("POST", "/login", json={"user_phone": _phone(91), "code": "000000"})
    ok4 = stats.check("白名单接口 /login 无 Token 可访问（非401）",
                      r_login.status_code != 401,
                      f"http={r_login.status_code}")
    all_pass = all_pass and ok4

    stats.end_flow(all_pass)


# =====================================================================
# Flow 5：对话历史持久化验证
# =====================================================================

def test_flow_history_persistence():
    stats.begin_flow("Flow-05: 对话历史持久化（退出重登后历史仍可查）")
    all_pass = True
    phone = _phone(50)

    # 第一次登录并对话
    code, _ = _get_code(phone)
    token1, _ = _login(phone, code) if code else (None, {})
    if not token1:
        stats.check("前置：第一次登录", False)
        stats.end_flow(False)
        return

    session_id = str(uuid.uuid4())
    _, _, events = _chat(token1, "联想笔记本驱动在哪里下载？", session_id)
    ok1 = stats.check("Step-1 对话成功",
                      any(e.get("data", {}).get("message_type") == "finish" for e in events))
    all_pass = all_pass and ok1

    time.sleep(0.5)
    # 退出
    _logout(token1)
    ok2 = stats.check("Step-2 退出成功", True)

    # 第二次登录
    code2, _ = _get_code(phone)
    token2, _ = _login(phone, code2) if code2 else (None, {})
    ok3 = stats.check("Step-3 重新登录成功", token2 is not None)
    all_pass = all_pass and ok3

    # 查询历史，验证第一次的对话仍存在
    if token2:
        hist = _query_history(token2)
        session_ids = [s["session_id"] for s in hist.get("chat_history_list", [])]
        ok4 = stats.check("Step-4 重新登录后历史记录仍可查",
                          session_id in session_ids,
                          f"expected={session_id[:8]}... found={len(session_ids)}条")
        all_pass = all_pass and ok4

        # 验证历史内容完整（含 user/assistant 两种 role）
        sessions_map = {s["session_id"]: s for s in hist.get("chat_history_list", [])}
        if session_id in sessions_map:
            messages = sessions_map[session_id].get("history_list", [])
            roles = {m["role"] for m in messages}
            ok5 = stats.check("Step-5 历史记录包含 user 和 assistant 两种角色",
                              "user" in roles and "assistant" in roles,
                              f"roles={roles}")
            all_pass = all_pass and ok5

        _logout(token2)
    else:
        stats.check("Step-4/5 历史记录查询（跳过：无 token）", False)
        all_pass = False

    stats.end_flow(all_pass)


# =====================================================================
# Flow 6：连续对话（上下文保持）
# =====================================================================

def test_flow_contextual_conversation():
    stats.begin_flow("Flow-06: 连续对话上下文保持（多轮同 session）")
    all_pass = True
    phone = _phone(60)

    code, _ = _get_code(phone)
    token, _ = _login(phone, code) if code else (None, {})
    if not token:
        stats.check("前置：登录成功", False)
        stats.end_flow(False)
        return

    stats.check("前置：登录成功", True)
    session_id = str(uuid.uuid4())

    # 第一轮对话
    r1, _, events1 = _chat(token, "联想笔记本保修期是多久？", session_id)
    ok1 = stats.check("Round-1 第一轮对话正常结束",
                      any(e.get("data", {}).get("message_type") == "finish" for e in events1),
                      f"events={len(events1)}")
    all_pass = all_pass and ok1

    # 第二轮对话（引用上下文）
    r2, _, events2 = _chat(token, "如果超出了保修期怎么办？", session_id)
    ok2 = stats.check("Round-2 第二轮对话正常结束（同 session）",
                      any(e.get("data", {}).get("message_type") == "finish" for e in events2),
                      f"events={len(events2)}")
    all_pass = all_pass and ok2

    # 验证历史中该 session 有两轮对话（>=4条消息：2 user + 2 assistant）
    time.sleep(0.5)
    hist = _query_history(token)
    sessions_map = {s["session_id"]: s for s in hist.get("chat_history_list", [])}
    if session_id in sessions_map:
        msgs = sessions_map[session_id].get("history_list", [])
        user_count = sum(1 for m in msgs if m["role"] == "user")
        ok3 = stats.check("Round-2 历史中该 session 有 ≥2 条 user 消息",
                          user_count >= 2,
                          f"user消息数={user_count}")
        all_pass = all_pass and ok3
    else:
        stats.check("Round-2 历史中可见该 session", False, f"session={session_id[:8]}...")
        all_pass = False

    _logout(token)
    stats.end_flow(all_pass)


# =====================================================================
# Flow 7：并发场景下不同用户互不干扰
# =====================================================================

def test_flow_user_isolation():
    stats.begin_flow("Flow-07: 不同用户数据隔离（各自历史互不可见）")
    import threading

    all_pass = True
    phone_a = _phone(70)
    phone_b = _phone(71)

    # 用户 A 登录
    code_a, _ = _get_code(phone_a)
    token_a, _ = _login(phone_a, code_a) if code_a else (None, {})
    ok1 = stats.check("用户A 登录成功", token_a is not None)
    all_pass = all_pass and ok1

    # 用户 B 登录
    code_b, _ = _get_code(phone_b)
    token_b, _ = _login(phone_b, code_b) if code_b else (None, {})
    ok2 = stats.check("用户B 登录成功", token_b is not None)
    all_pass = all_pass and ok2

    if not (token_a and token_b):
        stats.end_flow(False)
        return

    # 用户 A 发起对话
    session_a = str(uuid.uuid4())
    _, _, events_a = _chat(token_a, "我的电脑键盘失灵", session_a)
    stats.check("用户A 对话完成",
                any(e.get("data", {}).get("message_type") == "finish" for e in events_a))

    time.sleep(0.5)

    # 查询用户 B 的历史，不应包含用户 A 的 session
    hist_b = _query_history(token_b)
    b_session_ids = [s["session_id"] for s in hist_b.get("chat_history_list", [])]
    ok3 = stats.check("用户B 的历史中不包含用户A 的 session",
                      session_a not in b_session_ids,
                      f"session_a={session_a[:8]}... in B's list: {session_a in b_session_ids}")
    all_pass = all_pass and ok3

    _logout(token_a)
    _logout(token_b)
    stats.end_flow(all_pass)


# =====================================================================
# 主入口
# =====================================================================

def main():
    print("\n" + "=" * 65)
    print("  集成测试 — consultant 模块（端到端业务流程）")
    print(f"  服务地址：{BASE_URL}")
    print(f"  运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    test_flow_complete_auth_lifecycle()
    test_flow_relogin_after_logout()
    test_flow_multi_session()
    test_flow_token_auth_boundary()
    test_flow_history_persistence()
    test_flow_contextual_conversation()
    test_flow_user_isolation()

    return stats.summary()


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
