import json
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import settings
from infra.logging.logger import log


class SessionService:

    def get_history_list(self, user_id: str) -> list[dict[str, Any]]:
        """
        获取指定用户的所有历史会话列表
        :param user_id:
        :return:
        """
        try:
            # 用户的会话历史列表
            chat_history_file_list = []

            # 获取该user的所有.json历史对话文件，返回生成器
            chat_file_list = Path(settings.HISTORY_FILE_DIR).joinpath(user_id).glob("*.json")

            # 遍历生成器获取文件内容
            for file in chat_file_list:
                # 得到文件的session_id
                session_id = file.stem

                # 得到文件的时间
                file_time = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                try:
                    with file.open("r", encoding="utf-8") as f:
                        # 构建元组追加到历史对话列表
                        chat_history_file_list.append((session_id, file_time, json.load(f)))
                except Exception as e:
                    log.warning(f"文件读取失败: {str(e)}")
                    continue

            if not chat_history_file_list:
                log.info(f"用户：{user_id}，历史对话文件列表为空")
                return []

            chat_history_list = []

            for session_id, file_time, history_list in chat_history_file_list:
                # 历史对话列表有效则追加到历史对话列表
                if isinstance(history_list, list) and len(history_list) > 0:
                    non_system_chat_history_list \
                        = [chat_history for chat_history in history_list if chat_history.get("role") != "system"]
                    chat_history_list.append(
                        {
                            "session_id": session_id,
                            "file_time": file_time,
                            "history_list": non_system_chat_history_list
                        }
                    )

            # 按照时间排序
            return sorted(chat_history_list, key=lambda x: x["file_time"], reverse=True)
        except Exception as e:
            log.error(f"获取用户历史会话列表发生异常，用户ID: {user_id}，异常信息: {str(e)}")
            raise

    def del_chat_history(self, user_id: str, session_id: str):
        """
        删除指定用户的历史对话
        :param user_id:
        :param session_id:
        :return:
        """
        try:
            # 构建历史对话文件路径
            history_file_path = Path(settings.HISTORY_FILE_DIR).joinpath(user_id, f"{session_id}.json")

            # 如果文件存在，删除历史对话文件
            if history_file_path.exists():
                history_file_path.unlink()
                log.info(f"成功删除用户：{user_id}，会话ID：{session_id}的历史对话文件")
            else:
                log.warning(f"用户：{user_id}，会话ID：{session_id}的历史对话文件不存在，无法删除")
        except Exception as e:
            log.error(f"删除用户历史会话发生异常，用户ID: {user_id}，会话ID: {session_id}，异常信息: {str(e)}")
            raise


session_service = SessionService()

if __name__ == '__main__':
    for history in session_service.get_history_list("test_user_01"):
        print(history)
