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

            # 如果没有历史消息，使用默认的系统消息作为历史消息
            if not history_list:
                history_list = self._default_system_history_message()

            return history_list
        except JSONDecodeError as e:
            log.error(f"历史消息文件 {session_id}.json 格式错误，无法反序列化为 JSON: {str(e)}")
            return [{"role": "system", "content": "用户文件读取失败"}]
        except FileNotFoundError as e:
            log.error(f"历史消息文件 {session_id}.json 不存在: {str(e)}")
            return [{"role": "system", "content": "用户文件读取失败"}]
        except Exception as e:
            log.error(f"加载历史消息失败: {str(e)}")
            return [{"role": "system", "content": "用户文件读取失败"}]

    def _truncate_history(self, history_list: list[dict[str, Any]], truncate_num: int) -> list[dict[str, Any]]:
        """
        裁剪历史消息
        :param history_list:
        :param truncate_num:
        :return:
        """
        try:
            if not history_list:
                log.warning("历史消息列表为空，无法裁剪")
                return []

            # 分组系统历史消息和非系统历史消息
            system_message = []
            non_system_messages = []
            for history in history_list:
                if history.get("role", "") == "system":
                    system_message.append(history)
                else:
                    non_system_messages.append(history)

            if non_system_messages:
                # 裁剪指定轮数的非历史消息
                non_system_messages = non_system_messages[-truncate_num * 2:]

                # 合并系统消息和裁剪后的非系统消息
                history_list = system_message + non_system_messages

            return history_list
        except Exception as e:
            log.error(f"裁剪历史消息失败: {str(e)}")
            return history_list

    def _default_system_history_message(self) -> list[dict[str, Any]]:
        """
        默认历史会话消息
        :return:
        """
        return [{
            "role": "system",
            "content": "你是一个智能售后咨询助手，无论用户遇到什么样的技术售后咨询问题，都请尽力帮助他们找到解决方案。"
        }]

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
