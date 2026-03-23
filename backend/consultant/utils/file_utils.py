from pathlib import Path
from typing import Any

from config.settings import settings
from infra.logging.logger import log


def check_file_path(dir_path: str, file_path: str):
    """
    文件路径创建
    :param dir_path:
    :param file_path:
    :return:
    """
    try:
        file_path = Path(dir_path) / file_path

        return file_path
    except FileExistsError as e:
        log.error(f"文件路径创建错误: {file_path}")
        raise
    except OSError as e:
        log.error(f"文件系统错误: {str(e)}")
        raise
    except Exception as e:
        log.error(f"未知异常：{str(e)}")
        raise


def load_file(file_path: str) -> Any:
    """
    指定文件路径，加载该目录下的指定文件
    :param file_path:
    :return:
    """
    try:
        path = Path(file_path)
        if not path.exists():
            log.warning(f"文件路径不存在: {file_path}")
            return None

        # 路径是否有效
        if not path.is_file():
            log.warning(f"不是有效路径: {file_path}，要求是一个文件路径")
            return None

        # 分批次读取文件
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        log.error(f"文件操作错误: {str(e)}")
        return None
    except Exception as e:
        log.error(f"加载文件失败: {str(e)}")
        return None


def write_files(file_path: str, content: Any):
    """
    保存内容到指定文件
    :param file_path:
    :param content:
    :return:
    """
    try:
        path = Path(file_path)

        # 文件不存在目录，就重新创建
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        log.error(f"文件操作错误: {str(e)}")
        raise
    except Exception as e:
        log.error(f"写入文件失败: {str(e)}")
        raise


if __name__ == '__main__':
    prompt_content = load_file(settings.PROMPTS_FILE_DIR + "/consult_agent.md")
    print(prompt_content)
