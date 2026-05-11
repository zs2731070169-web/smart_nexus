import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from orjson.orjson import JSONEncodeError

from config.settings import settings
from infra.logging.logger import log
from utils import file_utils


def _get_history_messages_path(user_id: str, session_id: str) -> str:
    history_dir = Path(settings.HISTORY_FILE_DIR)
    return str(history_dir / user_id / f"{session_id}.json")


def _keep_first_and_recent(messages: list[dict[str, Any]], recent: int) -> list[dict[str, Any]]:
    # 首条 user 消息（任务/指代锚点）+ 最近 recent 条活跃上下文，丢弃中间冗余
    if not messages:
        return []
    # 取最近指定条数的消息
    tail = messages[-recent:]
    # 找到第一条 user 消息（任务/指代锚点）
    first = next((message for message in messages if message.get("role") == "user"), None)

    if first is None or first in tail:
        return tail
    return [first] + tail


class MemoryService:

    def load_history(self, user_id: str, session_id: str, truncate_num: int = 3) -> list[dict[str, Any]]:
        """
        加载用户历史对话记录
        :param user_id: # 用户唯一id
        :param session_id: # 每次会话的id
        :param truncate_num: 裁剪对话轮数
        :return:
        """
        # 读取历史消息
        history = self._read_history(user_id, session_id)

        # 裁剪历史消息
        truncated_history_messages = self._truncate_history(history, truncate_num)

        return truncated_history_messages

    def _read_history(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        """
        从文件里读取历史消息
        :param user_id:
        :param session_id:
        :return:
        """
        try:
            if not user_id or not user_id.strip():
                log.warning(f"用户ID无效，无法加载历史消息")
                return []

            # 创建文件路径
            file_path = _get_history_messages_path(user_id, session_id)

            # 读取文件
            history_list = file_utils.load_file(file_path)

            # 如果不是列表类型，反序列化为列表字典
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
        """
        按对话轮数分级压缩历史消息
        - 解决"全保留分散注意力 / 超上下文窗口 / 截断丢失指代锚点"三类问题
        - 以 truncate_num 为基准窗口，梯度放大；中长档采用 U 型保留（首条 user + 近期滑窗）
        """
        try:
            if not history_list:
                log.warning("历史消息列表为空，无法裁剪")
                return []

            # 分组系统消息和非系统消息，系统消息完整保留
            system_messages = [m for m in history_list if m.get("role", "") == "system"]
            messages = [m for m in history_list if m.get("role", "") != "system"]

            if not messages:
                return history_list

            # 一轮 = user + assistant 两条
            total_rounds = len(messages) // 2

            if total_rounds <= truncate_num:
                # 极短对话对话全保留
                kept = messages
            elif total_rounds <= truncate_num * 3:
                # 短对话：纯滑窗近 N 轮
                kept = messages[-truncate_num * 2:]
            elif total_rounds <= truncate_num * 6:
                # 中对话：（首+尾） = 首条 user 锚点 + 近 N 轮
                kept = _keep_first_and_recent(messages, recent=truncate_num * 2)
            else:
                # 长对话：（首+尾） + 收紧近期窗口防上下文溢出
                kept = _keep_first_and_recent(messages, recent=truncate_num)

            return system_messages + kept
        except Exception as e:
            log.error(f"裁剪历史消息失败: {str(e)}")
            return history_list

    def save_history(self, user_id: str, session_id: str, history_message: list[dict[str, Any]]) -> bool:
        """
        保存历史对话
        :param user_id:
        :param session_id:
        :param history_message:
        :return:
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

            # 创建文件路径
            file_path = _get_history_messages_path(user_id, session_id)

            # 序列化后存储里到消息列表
            file_utils.write_files(file_path, json.dumps(history_message, indent=2, ensure_ascii=False))

            return True
        except JSONEncodeError as e:
            log.error(f"历史消息无法序列化为 JSON 格式: {str(e)}")
            return False
        except Exception as e:
            log.error(f"保存历史消息失败: {str(e)}")
            return False


memory_service = MemoryService()
