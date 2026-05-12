import json
import re
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Optional

from orjson.orjson import JSONEncodeError

from config.settings import settings
from infra.logging.logger import log
from infra.memory.compressor import ContextCompressor
from utils import file_utils


class MemoryManager:
    """会话历史记忆服务。

    采用 hermes-agent 的"三段式压缩"思想，但适配本系统：
    - 触发时机：在 save_history 时压缩（用户已收到 SSE 完结帧），不影响首字节延迟
    - load_history 仅做读盘 + 兜底的轮数截断，保持同步以减少改造面
    - 摘要以一条特殊 system 消息持久化在同一文件中（无需新增审计文件）
    - 摘要失败时降级为纯截断（保留 head + tail），不阻塞主对话流
    """

    def __init__(self, compressor: Optional[ContextCompressor] = None) -> None:
        self._compressor = compressor

    def load_history(self, user_id: str, session_id: str, truncate_num: int = 3) -> list[dict[str, Any]]:
        """加载用户历史对话记录（同步、纯读取 + 防御性截断）。

        - 压缩后的摘要消息会原样保留并继续随历史一起喂给模型
        - 兜底截断逻辑保留：万一压缩失败/没触发，至少不会塞爆上下文窗口
        """
        history = self._read_history(user_id, session_id)
        truncated = self._truncate_history(history, truncate_num)
        return truncated

    async def save_history(self, user_id: str, session_id: str, history_message: list[dict[str, Any]]) -> bool:
        """保存历史对话。当 token 估算超阈值时触发压缩（异步、不阻塞 SSE）。

        压缩失败会降级为截断保留 head+tail，但本方法本身始终返回写盘结果。
        """
        try:
            if not history_message:
                log.warning("历史消息为空，无法保存")
                return False
            if not user_id or not user_id.strip():
                log.warning("用户ID无效，无法保存历史消息")
                return False
            if not session_id or not session_id.strip():
                log.warning("会话ID无效，无法保存历史消息")
                return False

            # 入库前剥离思维链：必须在压缩前，否则 token 估算与摘要器都会受 <think> 污染
            history_message = _strip_think_from_messages(history_message)

            # 压缩判断：仅当注入的消息列表，其token数量达到阈值时触发
            if self._compressor and self._compressor.should_compress(history_message):
                try:
                    # 执行压缩，并返回压缩后的消息列表
                    history_message = await self._compressor.compress(history_message)
                except Exception as e:
                    # 压缩自身异常 → 原样存盘，永不让记忆压缩影响主链路
                    log.error(f"上下文压缩异常，回退到原始历史: {str(e)}")

            file_path = _get_history_messages_path(user_id, session_id)
            file_utils.write_files(file_path, json.dumps(history_message, indent=2, ensure_ascii=False))
            return True
        except JSONEncodeError as e:
            log.error(f"历史消息无法序列化为 JSON 格式: {str(e)}")
            return False
        except Exception as e:
            log.error(f"保存历史消息失败: {str(e)}")
            return False

    # ------------------------------------------------------------------

    def _read_history(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        """从文件里读取历史消息"""
        try:
            if not user_id or not user_id.strip():
                log.warning(f"用户ID无效，无法加载历史消息")
                return []

            file_path = _get_history_messages_path(user_id, session_id)
            history_list = file_utils.load_file(file_path)

            if history_list and not isinstance(history_list, list):
                history_list = json.loads(history_list)

            return history_list or []
        except JSONDecodeError as e:
            log.error(f"历史消息文件 {session_id}.json 格式错误，无法反序列化为 JSON: {str(e)}")
            return []
        except FileNotFoundError as e:
            log.error(f"历史消息文件 {session_id}.json 不存在: {str(e)}")
            return []
        except Exception as e:
            log.error(f"加载历史消息失败: {str(e)}")
            return []

    def _truncate_history(self, history_list: list[dict[str, Any]], truncate_num: int) -> list[dict[str, Any]]:
        """兜底分级截断（仅在压缩未触发或失败时承担保护责任）

        与压缩器互补：
        - 压缩器看 token 阈值，能调 LLM 做语义保留
        - 截断器看轮数，无 LLM 依赖，纯结构性兜底
        """
        try:
            if not history_list:
                log.warning("历史消息列表为空，无法裁剪")
                return []

            # 系统消息（含压缩摘要）完整保留——它们是 head 锚点
            system_messages = [m for m in history_list if m.get("role", "") == "system"]
            messages = [m for m in history_list if m.get("role", "") != "system"]

            if not messages:
                return history_list

            total_rounds = len(messages) // 2

            # total_rounds ≤ 3 → 全保留
            if total_rounds <= truncate_num:
                kept = messages
            # 3 < total_rounds ≤ 9 → 只留最近 6 条
            elif total_rounds <= truncate_num * 3:
                kept = messages[-truncate_num * 2:]
            # 9 < total_rounds ≤ 18 → 首条 + 最近 6 条
            elif total_rounds <= truncate_num * 6:
                kept = _keep_first_and_recent(messages, recent=truncate_num * 2)
            # total_rounds > 18 → 首条 + 最近 3 条
            # 进入"过长对话"——这时基本说明压缩失败了（否则不会有 18 轮原文），降级为最严格保护：只留首条 + 最近 3
            else:
                kept = _keep_first_and_recent(messages, recent=truncate_num)
            """
            最终返回 = [system_prompt, SUMMARY, m1, m38, m39, m40]
                ↑           ↑      ↑     ↑
                系统设定    摘要   锚点   最近上下文
            """
            return system_messages + kept
        except Exception as e:
            log.error(f"裁剪历史消息失败: {str(e)}")
            return history_list


def _get_history_messages_path(user_id: str, session_id: str) -> str:
    history_dir = Path(settings.HISTORY_FILE_DIR)
    return str(history_dir / user_id / f"{session_id}.json")


def _keep_first_and_recent(messages: list[dict[str, Any]], recent: int) -> list[dict[str, Any]]:
    # 首条 user 消息（任务/指代锚点）+ 最近 recent 条活跃上下文，丢弃中间冗余
    if not messages:
        return []
    tail = messages[-recent:]
    first = next((message for message in messages if message.get("role") == "user"), None)
    if first is None or first in tail:
        return tail
    return [first] + tail


# 思维链标签匹配：剥离 assistant 的 <think>...</think>
# DOTALL 支持跨行（默认匹配到\n就会停止, DOTALL匹配到 . 才停止） / IGNORECASE 大小写不敏感
# 用非贪婪匹配，避免吞掉多个 think 块之间的有效内容
_THINK_PATTERN = re.compile(r"<think\b[^>]*>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def _strip_think(content: str) -> str:
    """剥离模型思维链，仅保留对外可见的最终回答。

    目的：assistant 消息入库前清洗，避免思维链回喂下一轮污染推理、浪费 token、泄露中间状态。
    """
    if not content or "<think" not in content.lower():
        return content
    return _THINK_PATTERN.sub("", content).strip()


def _strip_think_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """对 assistant 消息批量剥离思维链；其他角色原样保留。无 think 内容时返回原对象。"""
    cleaned: list[dict[str, Any]] = []
    for msg in messages:
        # 如果是ai回复的消息就进行清洗
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), str):
            # 去掉think标签
            new_content = _strip_think(msg["content"])
            # 如果新content和旧的content一样，说明ai回复的content没有think标签，就直接追加
            if new_content == msg["content"]:
                cleaned.append(msg)
            # 如果content里面是去掉think标签的新内容，就把新的content覆盖旧的content
            else:
                # 第一步：把 **msg 展开, 第二步：然后写 "content": new_content，后写的覆盖前面同名的
                cleaned.append({**msg, "content": new_content})
        # 不是ai回复的消息原样追加
        else:
            cleaned.append(msg)
    return cleaned
