import hashlib
import logging
import os
import re
from typing import Any

# 日志打印
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileUtils:


    @staticmethod
    def save_as_file(dir_path, filename, file_content) -> bool:
        """
        保存为文件
        :param filename:
        :param dir_path:
        :param file_content: 文件内容
        :return: 是否保存成功
        """
        try:
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
            # 合并路径
            file_path = os.path.join(dir_path, filename)
            # 保存文件到指定路径
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_content)
        except OSError as e:
            logger.error(e)
            return False
        except Exception as e:
            logger.error(e)
            return False
        return True


    @staticmethod
    def list_dir(dir_path: str) -> list:
        """
        列出目录下的文件
        :param dir_path: 目录路径
        :return: 文件列表
        """
        try:

            if not dir_path:
                logger.warning("目录路径为空")
                return []

            if not os.path.exists(dir_path):
                logger.warning(f"目录不存在: {dir_path}")
                return []

            if not os.path.isdir(dir_path):
                logger.warning(f"路径不是一个有效的目录: {dir_path}")
                return []

            filenames = os.listdir(dir_path)

            return [os.path.join(dir_path, filename) for filename in filenames]
        except PermissionError:
            logger.error(f"权限不足，无法访问目录: {dir_path}")
            return []
        except OSError as e:
            logger.error(f"遍历目录出错: {dir_path}, 原因: {e}")
            return []
        except Exception as e:
            logger.error(f"未知错误: {dir_path}, 原因: {e}")
            return []


    @staticmethod
    def remove_duplicate_files(files: list) -> list:
        """
        去除重复文件
        :param files:
        :return:
        """
        if not files:
            logger.warning("文件列表为空")
            return []

        file_list = []
        unique_files = set()

        try:
            for file in files:
                if not os.path.exists(file):
                    logger.warning(f"文件不存在，自动跳过: {file}")
                    continue

                if not os.path.isfile(file):
                    logger.warning(f"路径不是一个有效的文件，自动跳过: {file}")
                    continue

                # 计算file内容的hash值
                file_hash = FileUtils.md5_hash(file)

                if file_hash in unique_files:
                    logger.warning(f"发现重复文件，自动跳过: {file}")
                    continue

                unique_files.add(file_hash)
                file_list.append(file)

            logger.info(f"去重完成，原文件数: {len(files)}, 去重后文件数: {len(file_list)}")
            return file_list
        except OSError as e:
            logger.error(f"去重文件出错: 原文件数: {len(files)}, 原因: {e}")
            return []
        except Exception as e:
            logger.error(f"未知错误: 原文件数: {len(files)}, 原因: {e}")
            return []


    @staticmethod
    def md5_hash(file_path: str) -> str:
        """
        计算文件的hash值
        :param file_path: 文件路径
        :return: hash值
        """

        if not file_path:
            logger.warning("文件路径为空")
            return ""

        if not os.path.exists(file_path):
            logger.warning(f"文件不存在: {file_path}")
            return ""

        if not os.path.isfile(file_path):
            logger.warning(f"路径不是一个有效的文件: {file_path}")
            return ""

        try:
            md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5.update(chunk) # 更新读取的状态
                return md5.hexdigest() # 转为16进制hash值
        except OSError as e:
            logger.error(f"计算文件hash出错: {file_path}, 原因: {e}")
            return ""
        except Exception as e:
            logger.error(f"未知错误: {file_path}, 原因: {e}")
            return ""

    @staticmethod
    def list_file_metadata(dir_path: str) -> list[dict[str, Any]]:
        """
        使用目录路径获取该目录下所有文件的元信息
        :param self:
        :param dir_path:
        :return:
        """
        try:
            if not dir_path:
                logger.warning(f"目录路径不能为空")
                return []

            if not os.path.exists(dir_path):
                logger.warning(f"目录不存在: {dir_path}")
                return []

            if not os.path.isdir(dir_path):
                logger.warning(f"路径不是一个有效的目录: {dir_path}")
                return []

            filenames = os.listdir(dir_path)

            file_metadata_list = []

            for filename in filenames:
                file_path = os.path.join(dir_path, filename)
                if not os.path.isfile(file_path):
                    continue
                file_metadata_list.append(
                    {
                        "title": FileUtils.extract_filename(file_path),
                        "file_path": file_path
                    }
                )

            return file_metadata_list
        except OSError as e:
            logger.error(f"获取文件元信息出错: {dir_path}, 原因: {e}")
            return []
        except Exception as e:
            logger.error(f"未知错误: {dir_path}, 原因: {e}")
            return []

    @staticmethod
    def extract_filename(file_path: str) -> str:
        """
        根据文件路径提取文件名
        :param file_path:
        :return:
        """
        try:
            if not file_path:
                logger.warning("文件路径为空")
                return ""

            if not os.path.isfile(file_path):
                logger.warning(f"路径不是一个有效的文件: {file_path}")
                return ""

            filename = os.path.basename(file_path)
            # 提取文件格式xxx_xxx_xxx.md
            pattern = re.compile(r"^(.+?)_(.*?)$")
            match = pattern.fullmatch(filename)

            # 提取文件名（去除扩展名）
            if match:
                filename = match.group(2).strip()
                dot_index = filename.rfind(".")
                filename = filename[:dot_index] if dot_index > 0 else filename
            else:
                filename = os.path.splitext(filename)[0]
            return filename
        except OSError as e:
            logger.error(f"提取文件名出错: {file_path}, 原因:{e}")
            return ""
        except Exception as e:
            logger.error(f"未知错误: {file_path}, 原因: {e}")
            return ""
