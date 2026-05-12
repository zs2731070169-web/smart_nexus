"""记忆压缩与组织子模块。

参考 hermes-agent 的 ContextEngine 三段式思想（head 保护 + 中段 LLM 总结 + tail token 预算保护）
做最小必要适配：单一 token 预算压缩器 + 单一 MiniMax 摘要器，不引入 provider 抽象。
"""
from config.settings import settings
from infra.memory.compressor import ContextCompressor, TokenBudgetCompressor, SUMMARY_PREFIX
from infra.memory.memory_manager import MemoryManager
from infra.memory.summarizer import Summarizer, MiniMaxSummarizer

default_summarizer = MiniMaxSummarizer()
default_compressor = TokenBudgetCompressor(
    summarizer=default_summarizer,
    threshold_tokens=settings.MEMORY_COMPRESS_THRESHOLD_TOKENS,
    tail_token_budget=settings.MEMORY_COMPRESS_TAIL_TOKENS,
    protect_head_n=settings.MEMORY_COMPRESS_HEAD_N,
)

__all__ = [
    "ContextCompressor",
    "Summarizer",
    "SUMMARY_PREFIX",
    "MemoryManager",
    "default_compressor"
]
