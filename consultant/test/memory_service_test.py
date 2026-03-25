from pathlib import Path

from config.settings import settings
from infra.logging.logger import log
from service.memory_service import MemoryService

if __name__ == '__main__':
    import shutil

    svc = MemoryService()
    TEST_USER = "test_user_001"
    TEST_SESSION = "session_20260321"
    NEW_SESSION = "session_new_001"

    def setup():
        """在保存前手动创建用户目录（_get_history_messages_path 不自动建目录）"""
        user_dir = Path(settings.HISTORY_FILE_DIR) / TEST_USER
        user_dir.mkdir(parents=True, exist_ok=True)

    def cleanup():
        test_dir = Path(settings.HISTORY_FILE_DIR) / TEST_USER
        if test_dir.exists():
            shutil.rmtree(test_dir)
            log.info(f"[清理] 已删除测试目录: {test_dir}")

    setup()

    # ================================================================
    # 用例 1: 用户第一次进来（历史文件不存在）
    # 预期：返回只含一条默认系统消息的列表
    # ================================================================
    log.info("=" * 60)
    log.info("[用例 1] 用户第一次进来，历史文件不存在")
    result = svc.load_history(TEST_USER, TEST_SESSION)
    assert len(result) == 1 and result[0]["role"] == "system", f"预期只含默认系统消息，实际: {result}"
    log.info(f"结果（{len(result)} 条）: {result}")

    # ================================================================
    # 用例 2: 保存会话（写入 2 轮对话记录）
    # 预期：返回 True，文件成功写入
    # ================================================================
    log.info("=" * 60)
    log.info("[用例 2] 保存会话对话记录（2 轮）")
    messages_to_save = result + [
        {"role": "user",      "content": "电脑开机蓝屏怎么办？"},
        {"role": "assistant", "content": "可以尝试：1. 重启电脑；2. 检查最近安装的驱动程序..."},
        {"role": "user",      "content": "重启后还是蓝屏怎么办？"},
        {"role": "assistant", "content": "建议进入安全模式，卸载最近更新的驱动程序..."},
    ]
    ok = svc.save_history(TEST_USER, TEST_SESSION, messages_to_save)
    assert ok is True, "保存历史记录应返回 True"
    log.info(f"保存结果: {ok}")

    # ================================================================
    # 用例 3: 用户再次进来（读取已有会话全部历史）
    # 预期：返回全部 5 条消息（系统消息 + 2 轮对话）
    # ================================================================
    log.info("=" * 60)
    log.info("[用例 3] 用户再次进来，读取已有会话全部历史（truncate_num=10）")
    result = svc.load_history(TEST_USER, TEST_SESSION, truncate_num=10)
    assert len(result) == len(messages_to_save), f"预期 {len(messages_to_save)} 条，实际: {len(result)}"
    log.info(f"返回 {len(result)} 条消息:")
    for msg in result:
        log.info(f"  [{msg['role']}] {msg['content'][:40]}")

    # ================================================================
    # 用例 4: 历史记录裁剪（truncate_num=1，只保留最近 1 轮）
    # 预期：系统消息保留 + 最近 1 轮（2 条），共 3 条
    # ================================================================
    log.info("=" * 60)
    log.info("[用例 4] 历史记录裁剪（truncate_num=1，只保留最近 1 轮）")
    result = svc.load_history(TEST_USER, TEST_SESSION, truncate_num=1)
    assert len(result) == 3, f"预期 3 条（系统1 + 最近1轮2），实际: {len(result)}"
    assert result[0]["role"] == "system", "第一条应为系统消息"
    assert result[-1]["role"] == "assistant", "最后一条应为最近一轮的 assistant"
    log.info(f"裁剪后 {len(result)} 条: {[m['role'] for m in result]}")

    # ================================================================
    # 用例 5: 开启新会话（不同 session_id，历史文件不存在）
    # 预期：返回默认系统消息，与旧会话完全隔离
    # ================================================================
    log.info("=" * 60)
    log.info("[用例 5] 开启新会话（新 session_id，历史文件不存在）")
    result = svc.load_history(TEST_USER, NEW_SESSION)
    assert len(result) == 1 and result[0]["role"] == "system", f"新会话预期只含系统消息，实际: {result}"
    log.info(f"新会话初始消息: {result}")

    # ================================================================
    # 用例 6: session_id 为空白字符串 → 读写均回退到 default_session
    # 预期：save 返回 True，load 能读回写入的内容
    # ================================================================
    log.info("=" * 60)
    log.info("[用例 6] session_id 为空白字符串，读写均回退到 default_session")
    default_msgs = [
        {"role": "system",    "content": "你是一个智能售后咨询助手，无论用户遇到什么样的技术售后咨询问题，都请尽力帮助他们找到解决方案。"},
        {"role": "user",      "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮助您？"},
    ]
    ok = svc.save_history(TEST_USER, "   ", default_msgs)   # session_id 为空白
    assert ok is True, "session_id 为空白时应回退到 default_session 并保存成功"
    result = svc.load_history(TEST_USER, "   ")             # 同样用空白 session_id 读取
    assert len(result) == len(default_msgs), f"应读到 default_session 的 {len(default_msgs)} 条，实际: {len(result)}"
    log.info(f"default_session 读取到 {len(result)} 条消息")

    # ================================================================
    # 用例 7: user_id 为空，加载历史失败
    # 预期：返回空列表
    # ================================================================
    log.info("=" * 60)
    log.info("[用例 7] user_id 为空，无法加载历史")
    result = svc.load_history("", TEST_SESSION)
    assert result == [], f"user_id 为空应返回空列表，实际: {result}"
    log.info(f"结果: {result}")

    # ================================================================
    # 用例 8: user_id 为空，保存历史失败
    # 预期：返回 False
    # ================================================================
    log.info("=" * 60)
    log.info("[用例 8] user_id 为空，无法保存历史")
    ok = svc.save_history("", TEST_SESSION, messages_to_save)
    assert ok is False, "user_id 为空时应返回 False"
    log.info(f"结果: {ok}")

    # ================================================================
    # 用例 9: history_message 为空列表，保存失败
    # 预期：返回 False
    # ================================================================
    log.info("=" * 60)
    log.info("[用例 9] history_message 为空列表，无法保存")
    ok = svc.save_history(TEST_USER, TEST_SESSION, [])
    assert ok is False, "history_message 为空时应返回 False"
    log.info(f"结果: {ok}")

    cleanup()
    log.info("=" * 60)
    log.info("所有测试用例通过！")
