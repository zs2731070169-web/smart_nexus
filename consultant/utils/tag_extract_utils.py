from constants.enums import RenderType

# MiniMax 等模型把思考链以 <think>...</think> 内联在 output_text 流里，需要做流式拆分
THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"
# 缓冲区尾部可能是被截断的标签（如收到 "<thi"），最长保留 len(标签)-1 个字符等下次拼接
_PARTIAL_TAG_KEEP = max(len(THINK_OPEN), len(THINK_CLOSE)) - 1


def make_think_state() -> dict:
    """创建一个空的拆分状态，调用方需在整段流式过程中复用同一个 state。"""
    return {"in_think": False, "buf": ""}


def extract_think_tag(state: dict, delta: str) -> list[tuple[RenderType, str]]:
    """流式喂入一段 delta，返回 [(render_type, text), ...]。

    标签可能跨 delta 边界，因此 state["buf"] 末尾保留至多 _PARTIAL_TAG_KEEP
    个字符等待下一次拼接。
    """
    if not delta:
        return []
    # 合并多段delta，因为think标签可能被切到两段 delta 里，必须先合并，比如："你好<thi", "nk>分析中</think>结果"
    state["buf"] += delta
    out: list[tuple[RenderType, str]] = []

    # 循环找目标标签
    while True:
        # 先找 <think>， 再找 </think>，提取出<think>之前和<think></think>之间的思考内容到out列表，不存在<think>或</think>返回-1
        target = THINK_CLOSE if state["in_think"] else THINK_OPEN
        idx = state["buf"].find(target)
        # 找到（idx ≥ 0）
        if idx >= 0:
            # 把<think>前面或<think></think>标签之间的内容追加到 out
            before = state["buf"][:idx]
            if before:
                out.append((RenderType.THINKING if state["in_think"] else RenderType.ANSWER, before))
            # 把<think>或</think>后面的部分重新赋值给buf
            state["buf"] = state["buf"][idx + len(target):]
            # 翻转 in_think: False -> True, True -> False
            state["in_think"] = not state["in_think"]
            continue

        # 没有完整 <think> 或 </think> 标签，但末尾可能是部分标签，留住等下次
        keep = min(len(state["buf"]), _PARTIAL_TAG_KEEP)  # 末尾要留的字符数，最多 7，但 buf 比 7 还短就只能全留。
        safe_len = len(state["buf"]) - keep  # buf 前面绝对不可能是任何标签前缀的安全部分长度
        if safe_len > 0:
            safe = state["buf"][:safe_len]
            out.append((RenderType.THINKING if state["in_think"] else RenderType.ANSWER, safe))
            state["buf"] = state["buf"][safe_len:]
        break

    return out


def flush_think_tag(state: dict) -> list[tuple[RenderType, str]]:
    """
    流结束或切段时，把 buf 里那段"残留的片段输出"并清空buf
    """
    if not state["buf"]:
        return []
    tail = state["buf"]
    state["buf"] = ""
    return [(RenderType.THINKING if state["in_think"] else RenderType.ANSWER, tail)]


# ============================================================================
# 演示用例：直接 `python -m utils.tag_extract_utils` 运行，观察拆分过程
# ============================================================================
if __name__ == "__main__":
    def _tag(rt: RenderType) -> str:
        # 简化输出：A=ANSWER, T=THINKING
        return "A" if rt == RenderType.ANSWER else "T"


    def run_case(title: str, deltas: list[str]) -> None:
        """模拟一段 SSE 流：依次 feed 每个 delta，最后 flush。"""
        print(f"\n{'=' * 60}\n用例：{title}")
        print(f"原始流：{''.join(deltas)!r}")
        print("-" * 60)
        state = make_think_state()
        for i, d in enumerate(deltas, 1):
            out = extract_think_tag(state, d)
            print(f"  feed#{i} delta={d!r}")
            print(f"          → 输出 {[(_tag(r), t) for r, t in out]}")
            print(f"          → buf 残留={state['buf']!r}, in_think={state['in_think']}")
        tail = flush_think_tag(state)
        print(f"  flush   → 输出 {[(_tag(r), t) for r, t in tail]}")


    # 用例 1：最朴素 —— 一段 delta 内同时包含完整的 <think>...</think>
    run_case(
        "完整标签在同一段 delta 内",
        ["你好<think>分析中</think>结果"],
    )

    # 用例 2：标签被切成两段（最常见场景）—— "<thi" + "nk>..."
    # 第一段 feed 后，"<thi" 会作为部分标签留在 buf 里，等下一段拼接
    run_case(
        "<think> 开标签跨 delta 边界",
        ["你好<thi", "nk>分析中</think>结果"],
    )

    # 用例 3：</think> 闭标签也被切成两段
    run_case(
        "</think> 闭标签跨 delta 边界",
        ["<think>分析", "中</thi", "nk>最终回答"],
    )

    # 用例 4：一段 delta 内出现多对 <think>...</think>
    run_case(
        "一段 delta 内多对 think 标签",
        ["开头<think>思考1</think>中间<think>思考2</think>结尾"],
    )

    # 用例 5：流末尾恰好留了一小段不足 7 字符（小于 _PARTIAL_TAG_KEEP）
    # → feed 阶段不会下发，必须靠 flush 兜底
    run_case(
        "流尾残留不足 7 字符，依赖 flush 兜底",
        ["<think>思考</think>结果"],
    )

    # 用例 6：极端逐字符喂入 —— 验证状态机对任意切片都鲁棒
    raw = "前缀<think>推理</think>后缀"
    run_case(
        "逐字符喂入（每 delta 1 字符）",
        list(raw),
    )
