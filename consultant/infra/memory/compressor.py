"""上下文压缩器。

抽象基类 + 默认实现（TokenBudgetCompressor）。

核心思想：
1. 按 token 阈值触发，而非固定轮数——同样 6 条消息可能 500 字也可能 5 万字
2. 三段保护：
   - head：系统消息 + 首条 user（任务/指代锚点）——永不压缩
   - middle：LLM 结构化摘要替换
   - tail：按 token 预算反向累加保护近期上下文
3. 摘要作为一条带 SUMMARY_PREFIX 的 system 消息回填到历史，下次压缩时识别并作为
   previous_summary 传给摘要器实现"迭代更新"，多次压缩不丢失早期事实
4. 摘要失败时降级为纯截断（保留 head + tail），不阻塞主流程
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from infra.logging.logger import log
from infra.memory.summarizer import Summarizer


# 摘要消息前缀：插回 history 时用此前缀标记，下次压缩时据此识别 previous_summary
SUMMARY_PREFIX = "[CONTEXT SUMMARY — 历史对话压缩摘要]"

# 摘要消息使用的系统提示前缀，让主模型把它当背景而非新指令执行
_SUMMARY_NOTE = (
    "以下是早先对话经过压缩后的摘要，仅作为背景参考。"
    "**不要**回答摘要中提到的问题（它们已被处理过）。"
    "请只回应摘要之后出现的最新用户消息。"
)

# 粗略 token 估算：中英文混合按 3 字符/token
_CHARS_PER_TOKEN = 3


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """粗估消息列表的 token 数。"""
    total_chars = 0
    for msg in messages:
        content = msg.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        # 计算content本身的消息长度，额外再计算 8 个角色/特殊符号长度，这样后续估算的token数更接近真是长度
        total_chars += len(content) + 8
    return total_chars // _CHARS_PER_TOKEN


def is_summary_message(msg: dict[str, Any]) -> bool:
    """判断一条消息是否是我们之前压缩过的摘要。"""
    if msg.get("role") != "system":
        return False
    content = msg.get("content") or ""
    return isinstance(content, str) and content.startswith(SUMMARY_PREFIX)


class ContextCompressor(ABC):
    """上下文压缩器抽象基类。"""

    @abstractmethod
    def should_compress(self, messages: list[dict[str, Any]]) -> bool:
        """是否需要触发压缩。"""

    @abstractmethod
    async def compress(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """对 messages 执行压缩，返回压缩后的新消息列表。

        摘要以一条带 SUMMARY_PREFIX 的 system 消息回填，调用方直接持久化新列表即可。
        失败时降级为保护 head + tail 的纯截断。
        """


class TokenBudgetCompressor(ContextCompressor):
    """基于 token 预算的三段式压缩器。"""

    def __init__(
        self,
        summarizer: Summarizer,
        threshold_tokens: int = 8000,
        tail_token_budget: int = 2000,
        protect_head_n: int = 1,
        min_middle_msgs: int = 2,
    ) -> None:
        """
        :param summarizer: 中段摘要器
        :param threshold_tokens: 触发压缩的 token 阈值
        :param tail_token_budget: 保留尾部消息的最大 token 数（按字符估算反向累加）
        :param protect_head_n: 在非 system 消息中，保留的头部消息条数（一般为 1，即首条 user）
        :param min_middle_msgs: 中段至少 N 条非空消息才会调 LLM 总结，否则降级截断
        """
        self._summarizer = summarizer
        self._threshold_tokens = threshold_tokens
        self._tail_budget = tail_token_budget
        self._head_n = protect_head_n
        self._min_middle = min_middle_msgs

    def should_compress(self, messages: list[dict[str, Any]]) -> bool:
        """计算token数，用于作为是否需要压缩的条件"""
        return estimate_tokens(messages) >= self._threshold_tokens

    async def compress(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not messages:
            return messages

        # 系统消息
        system_msgs: list[dict[str, Any]] = []
        # 摘要消息
        previous_summary: Optional[str] = None
        # 普通对话
        dialogue: list[dict[str, Any]] = []

        for msg in messages:
            # 判断是否是摘要消息
            if is_summary_message(msg):
                # 获取旧摘要 previous_summary
                previous_summary = msg.get("content", "").removeprefix(SUMMARY_PREFIX).lstrip("\n").strip() or None
                continue
            # 判断是否是系统消息
            if msg.get("role") == "system":
                system_msgs.append(msg)
            # 默认是对话消息
            else:
                dialogue.append(msg)

        # 确定首部消息（作为指代锚点）
        head = dialogue[:self._head_n]

        # 确定 tail 消息，使用token数计算更加准确，用条数计算可能导致单条撑爆上下文窗口或者上下文语义不完整
        tail_start = self._find_tail_start(dialogue, self._head_n)
        # 截取尾部消息
        tail = dialogue[tail_start:]

        # 截取中段
        # 上一次压缩的 middle 已经被替换为摘要，不会再出现。但上一次压缩留下来的 tail，随着新对话累积，会逐渐变成新一轮的 middle
        middle = dialogue[self._head_n:tail_start]
        # 中段太短，没必要走 LLM，直接返回（保留全部对话 + 原摘要）
        if len(middle) < self._min_middle:
            log.info(f"压缩跳过：中段仅 {len(middle)} 条，低于阈值 {self._min_middle}")
            return self._assemble(system_msgs, previous_summary, head, middle, tail)

        log.info(
            f"上下文压缩触发 | 总消息: {len(messages)} | head: {len(head)} | "
            f"middle: {len(middle)} | tail: {len(tail)} | 估算 tokens: {estimate_tokens(messages)}"
        )

        # 让摘要器对中段生成摘要（迭代更新）
        new_summary = await self._summarizer.summarize(middle, previous_summary=previous_summary)

        # 摘要失败 → 降级为纯截断（middle 全丢，保留 head + tail + 旧摘要）
        if new_summary is None:
            log.warning("摘要生成失败，本次压缩降级为截断保留 head+tail")
            return self._assemble(system_msgs, previous_summary, head, [], tail)

        # 压缩成功，middle 全丢，head + tail + 新摘要
        return self._assemble(system_msgs, new_summary, head, [], tail)

    # ----------------------------------------------------------------------

    def _find_tail_start(self, dialogue: list[dict[str, Any]], head_end: int) -> int:
        """从尾部反向累加，找到 tail 起点索引。永远保护至少 2 条尾部消息。"""
        dialogue_length = len(dialogue)
        # 至少要保留的尾部消息条数
        min_tail = 2 if dialogue_length > head_end else 0
        # 累积token数
        total = 0
        tail_start = dialogue_length  # 初始tail 起点
        # 从最后一条（索引为 n-1）开始往前，停在 head_end - 1（不包括 head 本身）
        for i in range(dialogue_length - 1, head_end - 1, -1):
            content = dialogue[i].get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            # 估算这条消息的token数（+3 是元数据补偿）
            msg_tokens = len(content) // _CHARS_PER_TOKEN + 3
            # dialogue_length - i 剩下的消息条数满足最小保留消息条数，并且累加后，超出尾部保留的最大token数就停止累加
            # 反之，如果没有保留最小消息条数或没有超过最大尾部token数就继续累加
            if (dialogue_length - i) > min_tail and  total + msg_tokens > self._tail_budget:
                break
            # 累加token数
            total += msg_tokens
            # 更新tail起点，从后往前更新
            tail_start = i
        return tail_start

    @staticmethod
    def _assemble(
        system_msgs: list[dict[str, Any]],
        summary: Optional[str],
        head: list[dict[str, Any]],
        middle: list[dict[str, Any]],
        tail: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = list(system_msgs)
        if summary:
            result.append({
                "role": "system",
                "content": f"{SUMMARY_PREFIX}\n{_SUMMARY_NOTE}\n\n{summary}",
            })
        result.extend(head)
        result.extend(middle)
        result.extend(tail)
        return result
