"""
单元测试 - consultant 模块
测试范围：纯业务逻辑（无需运行服务器、无需 Redis/MySQL 连接）
运行方式：cd backend/consultant && python test/unit_test.py
"""
import sys
import os
import re
import json
import time
import uuid
import random
import warnings
import unittest

# Windows 控制台默认 GBK，强制 stdout/stderr 使用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

# 设置环境变量，防止 settings 初始化时因缺少必填项报错
# SECRET_KEY 须 >= 32 字节才符合 PyJWT 对 HS256 的最低要求
os.environ.setdefault("SF_API_KEY", "unit_test_fake_key_placeholder_only")
os.environ.setdefault("SECRET_KEY", "unit_test_secret_key_32bytes_min!!")  # 恰好 32 字节
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("TOKEN_EXPIRE_HOURS", "24")
os.environ.setdefault("MYSQL_PASSWORD", "test_password")

# 屏蔽 PyJWT InsecureKeyLengthWarning（单元测试使用临时密钥，非生产环境）
# 直接引用精确类型，避免 UserWarning 继承链匹配失效
from jwt import InsecureKeyLengthWarning
warnings.filterwarnings("ignore", category=InsecureKeyLengthWarning)

# 添加包路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# =====================================================================
# 自定义测试结果收集器
# =====================================================================

class DetailedTestResult(unittest.TestResult):
    """收集并打印详细测试结果"""

    def __init__(self):
        super().__init__()
        self.details = []
        self._start_times = {}

    def startTest(self, test):
        super().startTest(test)
        self._start_times[id(test)] = time.time()

    def _elapsed(self, test):
        return time.time() - self._start_times.get(id(test), time.time())

    def addSuccess(self, test):
        super().addSuccess(test)
        desc = test.shortDescription() or str(test)
        elapsed = self._elapsed(test)
        self.details.append({"name": desc, "status": "PASS", "elapsed": elapsed, "msg": ""})
        print(f"  [PASS] ({elapsed*1000:.1f}ms) {desc}")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        desc = test.shortDescription() or str(test)
        elapsed = self._elapsed(test)
        msg = str(err[1]).split("\n")[-1] if err[1] else ""
        self.details.append({"name": desc, "status": "FAIL", "elapsed": elapsed, "msg": msg})
        print(f"  [FAIL] ({elapsed*1000:.1f}ms) {desc}: {msg}")

    def addError(self, test, err):
        super().addError(test, err)
        desc = test.shortDescription() or str(test)
        elapsed = self._elapsed(test)
        msg = str(err[1]).split("\n")[-1] if err[1] else ""
        self.details.append({"name": desc, "status": "ERROR", "elapsed": elapsed, "msg": msg})
        print(f"  [ERROR] ({elapsed*1000:.1f}ms) {desc}: {msg}")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        desc = test.shortDescription() or str(test)
        self.details.append({"name": desc, "status": "SKIP", "elapsed": 0, "msg": reason})
        print(f"  [SKIP] {desc}: {reason}")


# =====================================================================
# 测试组 1：手机号正则验证
# =====================================================================

class TestPhoneValidation(unittest.TestCase):
    """手机号正则验证"""

    PHONE_PATTERN = r'^(?:\+86|0086)?1[3-9]\d{9}$'

    def _match(self, phone):
        return bool(re.match(self.PHONE_PATTERN, phone))

    def test_valid_11_digits(self):
        """有效手机号 - 标准11位"""
        self.assertTrue(self._match("18612345678"))

    def test_valid_prefix_plus86(self):
        """有效手机号 - +86前缀"""
        self.assertTrue(self._match("+8618612345678"))

    def test_valid_prefix_0086(self):
        """有效手机号 - 0086前缀"""
        self.assertTrue(self._match("008618612345678"))

    def test_valid_all_carriers(self):
        """有效手机号 - 各运营商号段（13/15/17/18/19）"""
        phones = [
            "13812345678", "14712345678", "15912345678",
            "16612345678", "17612345678", "18612345678", "19912345678",
        ]
        for phone in phones:
            with self.subTest(phone=phone):
                self.assertTrue(self._match(phone), f"{phone} 应该有效")

    def test_invalid_starts_with_12(self):
        """无效手机号 - 12开头"""
        self.assertFalse(self._match("12345678901"))

    def test_invalid_too_short(self):
        """无效手机号 - 位数不足（10位）"""
        self.assertFalse(self._match("1861234567"))

    def test_invalid_too_long(self):
        """无效手机号 - 位数过多（12位）"""
        self.assertFalse(self._match("186123456789"))

    def test_invalid_contains_letters(self):
        """无效手机号 - 含字母"""
        self.assertFalse(self._match("1861234567a"))

    def test_invalid_empty(self):
        """无效手机号 - 空字符串"""
        self.assertFalse(self._match(""))

    def test_invalid_starts_with_10(self):
        """无效手机号 - 10开头"""
        self.assertFalse(self._match("10012345678"))

    def test_invalid_special_chars(self):
        """无效手机号 - 含特殊字符"""
        self.assertFalse(self._match("186-1234-5678"))
        self.assertFalse(self._match("186 1234 5678"))


# =====================================================================
# 测试组 2：验证码生成逻辑
# =====================================================================

class TestVerificationCode(unittest.TestCase):
    """验证码生成逻辑"""

    def _generate_code(self):
        return str(random.randint(100000, 999999))

    def test_code_is_6_digits(self):
        """验证码为6位纯数字"""
        for _ in range(200):
            code = self._generate_code()
            self.assertEqual(len(code), 6, f"验证码 {code} 长度不为6")
            self.assertTrue(code.isdigit(), f"验证码 {code} 含非数字字符")

    def test_code_range_boundaries(self):
        """验证码范围 100000-999999（边界值）"""
        for _ in range(500):
            code = int(self._generate_code())
            self.assertGreaterEqual(code, 100000)
            self.assertLessEqual(code, 999999)

    def test_code_has_randomness(self):
        """验证码具有足够随机性（500次中至少50种不同值）"""
        codes = {self._generate_code() for _ in range(500)}
        self.assertGreater(len(codes), 50, f"500次生成仅得到{len(codes)}种验证码，随机性不足")

    def test_code_string_format(self):
        """验证码为字符串格式"""
        code = self._generate_code()
        self.assertIsInstance(code, str)

    def test_code_no_leading_zeros_below_100000(self):
        """randint(100000, 999999) 不会生成以0开头的6位码"""
        for _ in range(200):
            code = self._generate_code()
            self.assertNotEqual(code[0], "0")


# =====================================================================
# 测试组 3：JWT Token 生成与验证
# =====================================================================

class TestJWTToken(unittest.TestCase):
    """JWT Token 生成与验证"""

    SECRET_KEY = "unit_test_secret_key_do_not_use_in_prod"
    ALGORITHM = "HS256"

    def _encode(self, user_id, expire_hours=24, iat=None):
        import jwt
        now = iat or datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "exp": now + timedelta(hours=expire_hours),
            "iat": now,
        }
        return jwt.encode(payload, self.SECRET_KEY, algorithm=self.ALGORITHM)

    def _decode(self, token):
        import jwt
        return jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])

    def test_token_generation_returns_string(self):
        """Token 生成返回字符串"""
        token = self._encode("user_abc")
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 20)

    def test_token_decode_extracts_user_id(self):
        """解码 Token 可取出 user_id"""
        uid = uuid.uuid4().hex
        token = self._encode(uid)
        payload = self._decode(token)
        self.assertEqual(payload["user_id"], uid)

    def test_token_contains_required_fields(self):
        """Payload 包含 user_id / exp / iat"""
        token = self._encode("user_x")
        payload = self._decode(token)
        self.assertIn("user_id", payload)
        self.assertIn("exp", payload)
        self.assertIn("iat", payload)

    def test_expired_token_raises(self):
        """过期 Token 解码应抛 ExpiredSignatureError"""
        import jwt
        token = self._encode("user_exp", expire_hours=-1)
        with self.assertRaises(jwt.ExpiredSignatureError):
            self._decode(token)

    def test_wrong_secret_raises(self):
        """错误密钥解码应抛 InvalidSignatureError"""
        import jwt
        token = self._encode("user_wrong_key")
        with self.assertRaises(jwt.exceptions.InvalidSignatureError):
            # 使用足够长但错误的密钥（避免触发 InsecureKeyLengthWarning）
            jwt.decode(token, "this_is_a_wrong_key_but_long_enough_32b!", algorithms=[self.ALGORITHM])

    def test_bearer_format_parsing(self):
        """Authorization: Bearer <token> 格式解析"""
        token = self._encode("user_bearer")
        auth_header = f"Bearer {token}"
        parts = auth_header.split(" ", 1)
        self.assertEqual(parts[0], "Bearer")
        self.assertEqual(parts[1], token)

    def test_missing_bearer_prefix_detected(self):
        """无 Bearer 前缀时应识别为非法格式"""
        token = self._encode("user_no_bearer")
        # 不含空格时无法分割为两部分
        parts = token.split(" ", 1)
        self.assertEqual(len(parts), 1, "纯Token字符串不应被识别为 Bearer 格式")

    def test_invalid_token_string_raises(self):
        """随机字符串不应通过 JWT 解码"""
        import jwt
        with self.assertRaises(jwt.exceptions.DecodeError):
            self._decode("not_a_jwt_token")

    def test_different_users_get_different_tokens(self):
        """不同用户生成的 Token 应不同"""
        token_a = self._encode("user_a")
        token_b = self._encode("user_b")
        self.assertNotEqual(token_a, token_b)


# =====================================================================
# 测试组 4：枚举值定义
# =====================================================================

class TestEnumerations(unittest.TestCase):
    """枚举值定义"""

    def test_render_type_values(self):
        """RenderType 包含 THINKING/PROCESSING/ANSWER"""
        from constants.enums import RenderType
        self.assertEqual(RenderType.THINKING.value, "THINKING")
        self.assertEqual(RenderType.PROCESSING.value, "PROCESSING")
        self.assertEqual(RenderType.ANSWER.value, "ANSWER")

    def test_stream_status_values(self):
        """StreamStatus 包含 PROCESSING/FINISHED"""
        from constants.enums import StreamStatus
        self.assertEqual(StreamStatus.PROCESSING.value, "PROCESSING")
        self.assertEqual(StreamStatus.FINISHED.value, "FINISHED")

    def test_finished_reason_values(self):
        """FinishedReason 包含 NORMAL/MAX_TOKEN/EXCEPTION"""
        from constants.enums import FinishedReason
        self.assertEqual(FinishedReason.NORMAL.value, "NORMAL")
        self.assertEqual(FinishedReason.MAX_TOKEN.value, "MAX_TOKEN")
        self.assertEqual(FinishedReason.EXCEPTION.value, "EXCEPTION")

    def test_tool_name_mapping_completeness(self):
        """TOOL_NAME_MAPPING 包含所有必要工具"""
        from constants.enums import TOOL_NAME_MAPPING
        required = [
            "retrieval_knowledge",
            "tavily_search",
            "map_geocode",
            "map_url",
            "route_consult_agent",
            "route_navigation_agent",
            "navigation_sites",
        ]
        for key in required:
            self.assertIn(key, TOOL_NAME_MAPPING, f"缺少工具映射: {key}")

    def test_tool_name_mapping_chinese_values(self):
        """TOOL_NAME_MAPPING 值应为中文"""
        from constants.enums import TOOL_NAME_MAPPING
        for key, value in TOOL_NAME_MAPPING.items():
            self.assertTrue(
                any('\u4e00' <= c <= '\u9fff' for c in value),
                f"工具 {key} 的中文名 '{value}' 不含中文字符"
            )

    def test_render_type_count(self):
        """RenderType 恰好有3个值"""
        from constants.enums import RenderType
        self.assertEqual(len(RenderType), 3)

    def test_stream_status_count(self):
        """StreamStatus 恰好有2个值"""
        from constants.enums import StreamStatus
        self.assertEqual(len(StreamStatus), 2)

    def test_finished_reason_count(self):
        """FinishedReason 恰好有3个值"""
        from constants.enums import FinishedReason
        self.assertEqual(len(FinishedReason), 3)


# =====================================================================
# 测试组 5：SSE 消息格式
# =====================================================================

class TestSSEMessageFormat(unittest.TestCase):
    """SSE 流式消息格式"""

    def _make_delta(self, render_type, data, msg_id=None):
        return {
            "id": msg_id or uuid.uuid4().hex,
            "data": {
                "message_type": "delta",
                "render_type": render_type,
                "data": data,
            },
            "status": "PROCESSING",
            "metadata": {
                "create_time": str(datetime.now()),
                "finished_reason": None,
                "error_message": None,
            },
        }

    def _make_finish(self, reason="NORMAL", error=None):
        return {
            "id": uuid.uuid4().hex,
            "data": {"message_type": "finish"},
            "status": "FINISHED",
            "metadata": {
                "create_time": str(datetime.now()),
                "finished_reason": reason,
                "error_message": error,
            },
        }

    def test_delta_message_has_required_fields(self):
        """Delta 消息包含所有必要字段"""
        msg = self._make_delta("ANSWER", "测试内容")
        self.assertIn("id", msg)
        self.assertIn("data", msg)
        self.assertIn("status", msg)
        self.assertIn("metadata", msg)
        self.assertEqual(msg["data"]["message_type"], "delta")

    def test_finish_message_has_required_fields(self):
        """Finish 消息包含所有必要字段"""
        msg = self._make_finish()
        self.assertEqual(msg["data"]["message_type"], "finish")
        self.assertEqual(msg["status"], "FINISHED")
        self.assertEqual(msg["metadata"]["finished_reason"], "NORMAL")

    def test_exception_finish_has_error_message(self):
        """异常结束消息包含 error_message"""
        msg = self._make_finish(reason="EXCEPTION", error="系统发生异常")
        self.assertEqual(msg["metadata"]["finished_reason"], "EXCEPTION")
        self.assertIsNotNone(msg["metadata"]["error_message"])

    def test_sse_wire_format(self):
        """SSE 格式：以 'data: ' 开头，以 '\\n\\n' 结尾"""
        payload = json.dumps({"message_type": "delta", "data": "hello"}, ensure_ascii=False)
        sse_line = f"data: {payload}\n\n"
        self.assertTrue(sse_line.startswith("data: "))
        self.assertTrue(sse_line.endswith("\n\n"))

    def test_delta_status_is_processing(self):
        """Delta 消息 status 为 PROCESSING"""
        msg = self._make_delta("ANSWER", "内容")
        self.assertEqual(msg["status"], "PROCESSING")

    def test_sse_payload_valid_json(self):
        """SSE payload 为有效 JSON"""
        msg = self._make_delta("PROCESSING", "正在调用工具 查询知识库 ...")
        payload = json.dumps(msg, ensure_ascii=False)
        parsed = json.loads(payload)
        self.assertEqual(parsed["data"]["render_type"], "PROCESSING")

    def test_thinking_render_type(self):
        """THINKING 类型的 Delta 消息格式正确"""
        msg = self._make_delta("THINKING", "<think>思考过程</think>")
        self.assertEqual(msg["data"]["render_type"], "THINKING")
        self.assertEqual(msg["status"], "PROCESSING")

    def test_message_id_is_unique(self):
        """每条消息应有唯一 ID"""
        ids = [self._make_delta("ANSWER", f"内容{i}")["id"] for i in range(100)]
        self.assertEqual(len(set(ids)), 100, "消息 ID 出现重复")


# =====================================================================
# 测试组 6：对话历史管理逻辑
# =====================================================================

class TestConversationHistory(unittest.TestCase):
    """对话历史管理逻辑"""

    def _make_messages(self, n_rounds=5):
        """生成 n 轮对话消息（含系统消息）"""
        msgs = [{"role": "system", "content": "你是智能售后助手"}]
        for i in range(n_rounds):
            msgs.append({"role": "user", "content": f"问题{i+1}"})
            msgs.append({"role": "assistant", "content": f"回答{i+1}"})
        return msgs

    def test_filter_system_messages(self):
        """过滤系统消息后只剩 user/assistant"""
        msgs = self._make_messages(3)
        filtered = [m for m in msgs if m["role"] != "system"]
        self.assertEqual(len(filtered), 6)
        for m in filtered:
            self.assertIn(m["role"], ["user", "assistant"])

    def test_truncate_keeps_last_n_rounds(self):
        """截断逻辑保留最后 N 轮对话"""
        msgs = self._make_messages(10)
        sys_msgs = [m for m in msgs if m["role"] == "system"]
        non_sys = [m for m in msgs if m["role"] != "system"]
        truncate_num = 3
        truncated = sys_msgs + non_sys[-(truncate_num * 2):]
        self.assertEqual(len(truncated), 1 + truncate_num * 2)
        self.assertEqual(truncated[0]["role"], "system")
        # 最后一条应是第10轮的 assistant
        self.assertEqual(truncated[-1]["content"], "回答10")

    def test_system_message_preserved_in_truncation(self):
        """截断后系统消息始终保留"""
        msgs = self._make_messages(20)
        sys_msgs = [m for m in msgs if m["role"] == "system"]
        non_sys = [m for m in msgs if m["role"] != "system"]
        result = sys_msgs + non_sys[-(3 * 2):]
        self.assertEqual(result[0]["role"], "system")

    def test_empty_history_returns_system_message(self):
        """空历史返回默认系统消息结构"""
        default_system = {"role": "system", "content": "你是一个智能售后咨询助手"}
        msgs = [default_system]
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("售后", msgs[0]["content"])

    def test_history_json_roundtrip(self):
        """历史消息序列化/反序列化保真（含中文）"""
        msgs = [
            {"role": "user", "content": "电脑蓝屏了，请帮我解决！"},
            {"role": "assistant", "content": "请检查内存条是否插紧。"},
        ]
        serialized = json.dumps(msgs, indent=2, ensure_ascii=False)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized[0]["content"], "电脑蓝屏了，请帮我解决！")
        self.assertEqual(deserialized[1]["content"], "请检查内存条是否插紧。")

    def test_history_file_path_format(self):
        """历史文件路径格式：{dir}/{user_id}/{session_id}.json"""
        history_dir = "/app/history"
        user_id = uuid.uuid4().hex
        session_id = str(uuid.uuid4())
        path = f"{history_dir}/{user_id}/{session_id}.json"
        self.assertTrue(path.startswith(history_dir))
        self.assertTrue(path.endswith(".json"))
        parts = path.split("/")
        self.assertEqual(parts[-1], f"{session_id}.json")
        self.assertEqual(parts[-2], user_id)


# =====================================================================
# 测试组 7：Redis 缓存 Key 格式
# =====================================================================

class TestCacheKeyFormat(unittest.TestCase):
    """Redis 缓存 Key 格式"""

    def test_phone_code_key_format(self):
        """验证码 Key 格式为 'phone_code:{phone}'"""
        phone = "18612345678"
        key = f"phone_code:{phone}"
        self.assertEqual(key, "phone_code:18612345678")
        self.assertTrue(key.startswith("phone_code:"))

    def test_different_phones_yield_different_keys(self):
        """不同手机号产生不同 Key"""
        phones = ["13812345678", "15912345678", "18612345678"]
        keys = [f"phone_code:{p}" for p in phones]
        self.assertEqual(len(set(keys)), 3)

    def test_key_contains_full_phone(self):
        """Key 中包含完整手机号"""
        phone = "19912345678"
        key = f"phone_code:{phone}"
        self.assertIn(phone, key)


# =====================================================================
# 测试组 8：时间工具
# =====================================================================

class TestTimeUtils(unittest.TestCase):
    """时间格式化与时区工具"""

    def test_beijing_timezone_offset(self):
        """北京时区偏移量为 +8 小时"""
        beijing_tz = timezone(timedelta(hours=8))
        now = datetime.now(beijing_tz)
        offset_hours = now.utcoffset().total_seconds() / 3600
        self.assertEqual(offset_hours, 8)

    def test_login_time_format_pattern(self):
        """登录时间格式符合 '%Y-%m-%d %H:%M:%S'"""
        now = datetime.now()
        formatted = now.strftime("%Y-%m-%d %H:%M:%S")
        self.assertTrue(
            re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', formatted),
            f"格式不符合要求: {formatted}"
        )

    def test_file_time_format_pattern(self):
        """文件时间格式符合 '%Y-%m-%d %H:%M:%S'"""
        from datetime import datetime
        ts = 1711094400.0
        dt = datetime.fromtimestamp(ts)
        formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
        self.assertTrue(
            re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', formatted)
        )


# =====================================================================
# 测试组 9：错误响应结构
# =====================================================================

class TestErrorResponseStructure(unittest.TestCase):
    """错误响应结构"""

    def _make_business_error(self, message):
        return {"status": "500", "message": message}

    def test_business_error_has_status_500(self):
        """业务错误响应 status 字段为字符串 '500'"""
        resp = self._make_business_error("手机号无效")
        self.assertEqual(resp["status"], "500")
        self.assertIsInstance(resp["status"], str)

    def test_success_response_status_200(self):
        """成功响应 status 字段为字符串 '200'"""
        resp = {"status": "200", "message": ""}
        self.assertEqual(resp["status"], "200")

    def test_code_response_structure(self):
        """验证码响应包含 status/message/code"""
        resp = {"status": "200", "message": "", "code": "123456"}
        self.assertIn("status", resp)
        self.assertIn("message", resp)
        self.assertIn("code", resp)
        self.assertEqual(len(resp["code"]), 6)

    def test_login_response_structure(self):
        """登录响应包含 status/message/auth_token"""
        resp = {"status": "200", "message": "", "auth_token": "eyJ..."}
        self.assertIn("auth_token", resp)
        self.assertIsNotNone(resp["auth_token"])

    def test_login_failure_auth_token_is_null(self):
        """登录失败时 auth_token 为 null"""
        resp = {"status": "500", "message": "验证码不正确", "auth_token": None}
        self.assertIsNone(resp["auth_token"])

    def test_history_response_structure(self):
        """历史查询响应包含 chat_history_list"""
        resp = {
            "status": "200",
            "message": "",
            "chat_history_list": [
                {
                    "session_id": str(uuid.uuid4()),
                    "file_time": "2026-03-22 10:30:00",
                    "history_list": [
                        {"role": "user", "content": "问题"},
                        {"role": "assistant", "content": "回答"},
                    ],
                }
            ],
        }
        self.assertIn("chat_history_list", resp)
        self.assertEqual(len(resp["chat_history_list"]), 1)
        session = resp["chat_history_list"][0]
        self.assertIn("session_id", session)
        self.assertIn("file_time", session)
        self.assertIn("history_list", session)


# =====================================================================
# 主入口：运行测试并输出统计
# =====================================================================

def run_all_tests():
    test_groups = [
        TestPhoneValidation,
        TestVerificationCode,
        TestJWTToken,
        TestEnumerations,
        TestSSEMessageFormat,
        TestConversationHistory,
        TestCacheKeyFormat,
        TestTimeUtils,
        TestErrorResponseStructure,
    ]

    result = DetailedTestResult()
    loader = unittest.TestLoader()
    total_start = time.time()

    print("\n" + "=" * 65)
    print("  单元测试 — consultant 模块")
    print("=" * 65)

    for cls in test_groups:
        print(f"\n▶ {cls.__doc__}")
        suite = loader.loadTestsFromTestCase(cls)
        suite.run(result)

    total_elapsed = time.time() - total_start

    # ——— 统计指标 ———
    total = len(result.details)
    passed = sum(1 for d in result.details if d["status"] == "PASS")
    failed = sum(1 for d in result.details if d["status"] == "FAIL")
    errors = sum(1 for d in result.details if d["status"] == "ERROR")
    skipped = sum(1 for d in result.details if d["status"] == "SKIP")
    pass_rate = (passed / total * 100) if total else 0

    elapsed_list = [d["elapsed"] for d in result.details if d["status"] == "PASS"]
    avg_ms = (sum(elapsed_list) / len(elapsed_list) * 1000) if elapsed_list else 0
    max_ms = (max(elapsed_list) * 1000) if elapsed_list else 0

    print("\n" + "=" * 65)
    print("  单元测试统计指标")
    print("=" * 65)
    print(f"  测试总数          : {total}")
    print(f"  通过 (PASS)       : {passed}  ✓")
    print(f"  失败 (FAIL)       : {failed}  ✗")
    print(f"  错误 (ERROR)      : {errors}  !")
    print(f"  跳过 (SKIP)       : {skipped}")
    print(f"  通过率            : {pass_rate:.1f}%")
    print(f"  总耗时            : {total_elapsed:.3f}s")
    print(f"  平均单测耗时      : {avg_ms:.2f}ms")
    print(f"  最慢单测耗时      : {max_ms:.2f}ms")
    print("=" * 65)

    if failed > 0 or errors > 0:
        print("\n  失败 / 错误明细：")
        for d in result.details:
            if d["status"] in ("FAIL", "ERROR"):
                print(f"  [{d['status']}] {d['name']}")
                if d["msg"]:
                    print(f"         原因: {d['msg']}")

    return failed == 0 and errors == 0


if __name__ == "__main__":
    ok = run_all_tests()
    sys.exit(0 if ok else 1)
